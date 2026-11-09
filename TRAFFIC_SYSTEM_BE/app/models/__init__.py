"""SQLModel table models. Importing this package registers every table
with ``SQLModel.metadata`` so ``init_db()`` creates them all."""

from app.models.enums import PlaceType, UserRole
from app.models.saved_place import SavedPlace
from app.models.search_history import SearchHistory
from app.models.user import User

__all__ = [
    "PlaceType",
    "SavedPlace",
    "SearchHistory",
    "User",
    "UserRole",
]
