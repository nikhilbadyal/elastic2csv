"""Client to interact with Elasticsearch."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import elasticsearch

from esxport.constant import CONNECTION_TIMEOUT
from esxport.exceptions import ScrollExpiredError

if TYPE_CHECKING:
    from typing_extensions import Self

    from esxport.click_opt.cli_options import CliOptions


class ElasticsearchClient:
    """Elasticsearch client."""

    def __init__(
        self: Self,
        cli_options: CliOptions,
    ) -> None:
        self.client = elasticsearch.Elasticsearch(
            hosts=cli_options.url,
            request_timeout=CONNECTION_TIMEOUT,
            basic_auth=(cli_options.user, cli_options.password),
            verify_certs=cli_options.verify_certs,
            ca_certs=cli_options.ca_certs,
            client_cert=cli_options.client_cert,
            client_key=cli_options.client_key,
        )

    def indices_exists(self: Self, index: str) -> bool:
        """Check if a given index exists."""
        return bool(self.client.indices.exists(index=index))

    def get_mapping(self: Self, index: str) -> dict[str, Any]:
        """Get the mapping for a given index."""
        return self.client.indices.get_mapping(index=index).raw

    def search(self: Self, **kwargs: Any) -> Any:
        """Search in the index."""
        return self.client.search(**kwargs)

    def scroll(self: Self, scroll: str, scroll_id: str) -> Any:
        """Paginated the search results."""
        try:
            return self.client.scroll(scroll=scroll, scroll_id=scroll_id)
        except elasticsearch.NotFoundError as e:
            msg = f"Scroll {scroll_id} expired."
            raise ScrollExpiredError(msg) from e

    def clear_scroll(self: Self, scroll_id: str) -> None:
        """Remove all scrolls."""
        self.client.clear_scroll(scroll_id=scroll_id)