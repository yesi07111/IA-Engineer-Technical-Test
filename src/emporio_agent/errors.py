class EmporioError(Exception):
    """Base error of the project.

    Every error raised on purpose by the agent inherits from this one, so the
    interfaces can catch them all in a single place.
    """


class DataLoadError(EmporioError):
    """Raised when a data file is missing, unreadable or has invalid rows."""


class ConfigurationError(EmporioError):
    """Raised when the settings are incomplete or point to something that does not exist."""
