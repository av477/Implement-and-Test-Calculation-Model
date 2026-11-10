"""Database operations used by the API."""

from app.operations.calculations import (
    UserNotFoundError,
    create_calculation,
    get_calculation,
    list_calculations,
    update_calculation,
)
from app.operations.users import (
    DuplicateUserError,
    authenticate_user,
    create_user,
    get_user,
    get_user_by_login,
    get_user_with_calculations,
)

__all__ = [
    "DuplicateUserError",
    "UserNotFoundError",
    "authenticate_user",
    "create_calculation",
    "create_user",
    "get_calculation",
    "get_user",
    "get_user_by_login",
    "get_user_with_calculations",
    "list_calculations",
    "update_calculation",
]
