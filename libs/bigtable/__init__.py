"""Bigtable KNN vector-search integration (search_backend=bigtable)."""

from .client import BigtableClient, get_bt_client

__all__ = ["BigtableClient", "get_bt_client"]
