"""Main export module."""
import contextlib
import json
import sys
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, Self, TypeVar

from elasticsearch.exceptions import ConnectionError
from loguru import logger
from tqdm import tqdm

from src.click_opt.cli_options import CliOptions
from src.constant import FLUSH_BUFFER, RETRY_DELAY, TIMES_TO_TRY
from src.elastic import ElasticsearchClient
from src.exceptions import IndexNotFoundError
from src.writer import Writer

F = TypeVar("F", bound=Callable[..., Any])


# Retry decorator for functions with exceptions
def retry(
    exception_to_check: type[BaseException],
    tries: int = TIMES_TO_TRY,
    delay: int = RETRY_DELAY,
) -> Callable[[F], F]:
    """Retryn connection."""

    def deco_retry(f: Any) -> Any:
        @wraps(f)
        def f_retry(*args: Any, **kwargs: dict[Any, Any]) -> Any:
            mtries = tries
            while mtries > 0:
                try:
                    return f(*args, **kwargs)
                except exception_to_check as e:
                    logger.error(e)
                    logger.info(f"Retrying in {delay} seconds ...")
                    time.sleep(delay)
                    mtries -= 1
            try:
                return f(*args, **kwargs)
            except exception_to_check as e:
                logger.exception(f"Fatal Error: {e}")
                sys.exit(1)

        return f_retry

    return deco_retry


class EsXport(object):
    """Main class."""

    def __init__(self: Self, opts: CliOptions, es_client: ElasticsearchClient) -> None:
        self.search_args: dict[str, Any] = {}
        self.opts = opts
        self.num_results = 0
        self.scroll_ids: list[str] = []
        self.scroll_time = "30m"
        self.tmp_file = f"{opts.output_file}.tmp"
        self.rows_written = 0

        self.es_client = es_client

    @retry(ConnectionError, tries=TIMES_TO_TRY)
    def _check_indexes(self: Self) -> None:
        """Check if input indexes exist."""
        indexes = self.opts.index_prefixes
        if "_all" in indexes:
            indexes = ["_all"]
        else:
            indexes_status = self.es_client.indices_exists(index=indexes)
            if not indexes_status:
                msg = f"Any of index(es) {', '.join(self.opts.index_prefixes)} does not exist in {self.opts.url}."
                raise IndexNotFoundError(
                    msg,
                )
        self.opts.index_prefixes = indexes

    def _validate_fields(self: Self) -> None:
        all_fields_dict: dict[str, list[str]] = {}
        indices_names = list(self.opts.index_prefixes)
        all_expected_fields = self.opts.fields.copy()
        for sort_query in self.opts.sort:
            sort_key = next(iter(sort_query.keys()))
            parts = sort_key.split(".")
            sort_param = parts[0] if len(parts) > 0 else sort_key
            all_expected_fields.append(sort_param)
        if "_all" in all_expected_fields:
            all_expected_fields.remove("_all")

        for index in indices_names:
            response: dict[str, Any] = self.es_client.get_mapping(index=index)
            all_fields_dict[index] = []
            for field in response[index]["mappings"]["properties"]:
                all_fields_dict[index].append(field)
        all_es_fields = {value for values_list in all_fields_dict.values() for value in values_list}

        for element in all_expected_fields:
            if element not in all_es_fields:
                logger.error(f"Fields {element} doesn't exist in any index.")
                sys.exit(1)

    def _prepare_search_query(self: Self) -> None:
        """Prepares search query from input."""
        self.search_args = {
            "index": ",".join(self.opts.index_prefixes),
            "scroll": self.scroll_time,
            "size": self.opts.scroll_size,
            "terminate_after": self.opts.max_results,
            "body": self.opts.query,
        }
        if self.opts.sort:
            self.search_args["sort"] = self.opts.sort

        if "_all" not in self.opts.fields:
            self.search_args["_source_includes"] = ",".join(self.opts.fields)

        if self.opts.debug:
            logger.debug("Using these indices: {}.".format(", ".join(self.opts.index_prefixes)))
            logger.debug(f"Query {self.opts.query}")
            logger.debug("Output field(s): {}.".format(", ".join(self.opts.fields)))
            logger.debug(f"Sorting by: {self.opts.sort}.")

    @retry(ConnectionError, tries=TIMES_TO_TRY)
    def next_scroll(self: Self, scroll_id: str) -> Any:
        """Paginate to the next page."""
        return self.es_client.scroll(scroll=self.scroll_time, scroll_id=scroll_id)

    def _write_to_temp_file(self: Self, res: Any) -> None:
        """Write to temp file."""
        hit_list = []
        total_size = int(min(self.opts.max_results, self.num_results))
        bar = tqdm(
            desc=self.tmp_file,
            total=total_size,
            unit="docs",
            colour="green",
        )

        while self.rows_written != total_size:
            if res["_scroll_id"] not in self.scroll_ids:
                self.scroll_ids.append(res["_scroll_id"])

            if not res["hits"]["hits"]:
                logger.info("Scroll[{}] expired(multiple reads?). Saving loaded data.".format(res["_scroll_id"]))
                break
            for hit in res["hits"]["hits"]:
                self.rows_written += 1
                bar.update(1)
                hit_list.append(hit)
                if len(hit_list) == FLUSH_BUFFER:
                    self._flush_to_file(hit_list)
                    hit_list = []
            res = self.next_scroll(res["_scroll_id"])
        bar.close()
        self._flush_to_file(hit_list)

    @retry(ConnectionError, tries=TIMES_TO_TRY)
    def search_query(self: Self) -> Any:
        """Search the index."""
        self._validate_fields()
        self._prepare_search_query()
        res = self.es_client.search(**self.search_args)
        self.num_results = res["hits"]["total"]["value"]

        logger.info(f"Found {self.num_results} results.")

        if self.num_results > 0:
            self._write_to_temp_file(res)

    def _flush_to_file(self: Self, hit_list: list[dict[str, Any]]) -> None:
        """Flush the search results to a temporary file."""

        def add_meta_fields() -> None:
            if self.opts.meta_fields:
                for fields in self.opts.meta_fields:
                    data[fields] = hit.get(fields, None)

        with Path(self.tmp_file).open(mode="a", encoding="utf-8") as tmp_file:
            for hit in hit_list:
                data = hit["_source"]
                data.pop("_meta", None)
                add_meta_fields()
                tmp_file.write(json.dumps(data))
                tmp_file.write("\n")

    def _clean_scroll_ids(self: Self) -> None:
        """Clear all scroll ids."""
        with contextlib.suppress(Exception):
            self.es_client.clear_scroll(scroll_id="_all")

    def _export(self: Self) -> None:
        """Export the data."""
        with Path(self.tmp_file).open() as f:
            first_line = json.loads(f.readline().strip("\n"))
            csv_headers = first_line.keys()
        Writer.write_to_csv(
            csv_header=csv_headers,
            total_records=self.rows_written,
            out_file=self.opts.output_file,
            delimiter=self.opts.delimiter,
        )

    def export(self: Self) -> None:
        """Export the data."""
        self._check_indexes()
        self.search_query()
        self._clean_scroll_ids()
        self._export()