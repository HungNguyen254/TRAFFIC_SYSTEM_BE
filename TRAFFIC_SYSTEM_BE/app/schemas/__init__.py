"""Schemas live in a single module: ``app.schemas.schema``."""

from app.schemas.schema import (
    CoordinatePoint,
    SavedPlaceCreate,
    SavedPlaceRead,
    SavedPlaceUpdate,
    SearchHistoryCreate,
    SearchHistoryRead,
    UserCreate,
    UserRead,
    UserRegister,
    UserUpdate,
)

__all__ = [
    "CoordinatePoint",
    "SavedPlaceCreate",
    "SavedPlaceRead",
    "SavedPlaceUpdate",
    "SearchHistoryCreate",
    "SearchHistoryRead",
    "UserCreate",
    "UserRead",
    "UserRegister",
    "UserUpdate",
]
