"""Error types for cfaxis."""


class ClimError(Exception):
    """Base error for cfaxis operations."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


class IoError(ClimError):
    pass


class JsonError(ClimError):
    pass


class TomlError(ClimError):
    pass


class ParseError(ClimError):
    pass


class FormatError(ClimError):
    pass


class ValidationError(ClimError):
    pass


class IncompatibleAppendError(ClimError):
    pass


class CalendarAxisConflictError(ClimError):
    pass


class UnsupportedCalendarError(ClimError):
    pass
