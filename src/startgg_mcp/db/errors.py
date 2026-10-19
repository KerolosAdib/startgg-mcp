class DatabaseUnavailable(Exception):
    """The database could not be reached, or did not wake up in time."""


class QueryTooSlow(Exception):
    """A query ran past the statement timeout."""
