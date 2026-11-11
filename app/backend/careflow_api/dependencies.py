
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from careflow_api.storage import (
    users,
    doctors,
    appointments,
)
from careflow_api.security import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> dict:
    """Validate the JWT and retrieve the authenticated user."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        email = payload.get("sub")

        if not email:
            raise unauthorized

        # Retrieve the user through the domain-specific repository.
        user = users.get_by_email(email)

        if user is None:
            raise unauthorized

        # Ensure the JWT role matches the current database role.
        if user["role"] != payload.get("role"):
            raise unauthorized

        return user

    except (jwt.InvalidTokenError, KeyError, TypeError):
        raise unauthorized


def require_role(*allowed_roles: str):
    """Restrict access to users with the specified roles."""

    def role_checker(
        current_user: Annotated[
            dict,
            Depends(get_current_user),
        ],
    ) -> dict:

        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return role_checker
