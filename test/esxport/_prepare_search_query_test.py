"""Export testing."""
import string
from random import choice, randint
from typing import Any
from unittest.mock import patch

from src.click_opt.cli_options import CliOptions
from src.elastic import ElasticsearchClient
from src.esxport import EsXport


@patch("src.esxport.EsXport._validate_fields")
class TestSearchQuery:
    """Tests that a search query with valid input parameters is successful."""

    @staticmethod
    def random_string(str_len: int = 20) -> str:
        """Generates a random string."""
        characters = string.ascii_letters + string.digits
        return "".join(choice(characters) for _ in range(str_len))

    @staticmethod
    def random_number(upper: int = 100, lower: int = 10000) -> int:
        """Generates a random number."""
        return randint(upper, lower)

    def test_index(
        self: "TestSearchQuery",
        _: Any,
        mock_es_client: ElasticsearchClient,
        cli_options: CliOptions,
    ) -> None:
        """Arr, matey!.

        Let's test if our search query be successful, with valid input parameters!.
        """
        random_strings = [self.random_string(10) for _ in range(5)]
        cli_options.index_prefixes = random_strings
        indexes = ",".join(random_strings)

        es_export = EsXport(cli_options, mock_es_client)
        es_export._prepare_search_query()
        assert es_export.search_args["index"] == indexes

    def test_size(
        self: "TestSearchQuery",
        _: Any,
        mock_es_client: ElasticsearchClient,
        cli_options: CliOptions,
    ) -> None:
        """Arr, matey!.

        Let's test if our search query be successful, with valid input parameters!.
        """
        page_size = randint(100, 9999)
        cli_options.scroll_size = page_size

        es_export = EsXport(cli_options, mock_es_client)
        es_export._prepare_search_query()
        assert es_export.search_args["size"] == page_size

    def test_query(
        self: "TestSearchQuery",
        _: Any,
        mock_es_client: ElasticsearchClient,
        cli_options: CliOptions,
    ) -> None:
        """Arr, matey!.

        Let's test if our search query be successful, with valid input parameters!.
        """
        expected_query: dict[str, Any] = {"query": {"match_all": {}}}
        cli_options.query = expected_query

        es_export = EsXport(cli_options, mock_es_client)
        es_export._prepare_search_query()
        assert es_export.search_args["body"] == expected_query

    def test_terminate_after(
        self: "TestSearchQuery",
        _: Any,
        mock_es_client: ElasticsearchClient,
        cli_options: CliOptions,
    ) -> None:
        """Arr, matey!.

        Let's test if our search query be successful, with valid input parameters!.
        """
        random_max = self.random_number()
        cli_options.max_results = random_max

        es_export = EsXport(cli_options, mock_es_client)
        es_export._prepare_search_query()
        assert es_export.search_args["terminate_after"] == random_max

    def test_sort(
        self: "TestSearchQuery",
        _: Any,
        mock_es_client: ElasticsearchClient,
        cli_options: CliOptions,
    ) -> None:
        """Arr, matey!.

        Let's test if our search query be successful, with valid input parameters!.
        """
        random_sort = [{self.random_string(): "asc"}, {self.random_string(): "desc"}]
        cli_options.sort = random_sort

        es_export = EsXport(cli_options, mock_es_client)
        es_export._prepare_search_query()
        assert es_export.search_args["sort"] == random_sort
