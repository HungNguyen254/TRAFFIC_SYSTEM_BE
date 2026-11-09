from enum import StrEnum


class UserRole(StrEnum):
    """Role of an account in the traffic system."""

    USER = "USER"
    ADMIN = "ADMIN"


class PlaceType(StrEnum):
    """Kind of place the user can save."""

    HOME = "HOME"
    COMPANY = "COMPANY"
    OTHER = "OTHER"
