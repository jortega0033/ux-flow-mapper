"""Error type shared by storage and the HTTP layer."""


class ApiError(Exception):
    """An error that maps directly to an HTTP status and error code."""

    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
