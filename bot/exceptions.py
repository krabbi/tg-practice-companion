"""Domain exceptions for tg-practice-companion."""


class PracticeCompanionError(Exception):
    """Base class for all domain errors."""


class TimezoneError(PracticeCompanionError):
    """Raised when an invalid or unsupported IANA timezone is provided."""


class DeliveryError(PracticeCompanionError):
    """Raised when a practice delivery (send) fails."""


class MediaAssetError(PracticeCompanionError):
    """Raised when a media asset is missing required fields."""
