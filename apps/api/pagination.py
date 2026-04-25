"""Pagination classes.

`StandardPagination`: limit/offset for catalogue endpoints (instruments, sources, news).
`TimeseriesCursorPagination`: keyset over `ts` for partitioned candle scans.
"""
from rest_framework.pagination import CursorPagination, LimitOffsetPagination


class StandardPagination(LimitOffsetPagination):
    default_limit = 100
    max_limit = 1000


class TimeseriesCursorPagination(CursorPagination):
    """Cursor on `-ts` — only safe for models with a `ts` field."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000
    ordering = "-ts"
    cursor_query_param = "cursor"


class NewsCursorPagination(CursorPagination):
    """Cursor on `-published_at`."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = "-published_at"
    cursor_query_param = "cursor"
