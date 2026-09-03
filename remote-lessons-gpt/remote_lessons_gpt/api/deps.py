from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth_utils import ADMIN_ROLES, decode_access_token
from .job_store import JobStore

_bearer = HTTPBearer(auto_error=False)


def get_store() -> JobStore:
    from . import app as api_app
    return api_app.store


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    store: Annotated[JobStore, Depends(get_store)],
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        payload = decode_access_token(creds.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = store.get_user(str(payload.get("sub")))
    if not user or not user.get("is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_admin_sse(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    store: Annotated[JobStore, Depends(get_store)],
    token: Annotated[str | None, Query()] = None,
) -> dict:
    if creds and creds.credentials:
        return get_current_user(creds, store)
    if token:
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
        user = store.get_user(str(payload.get("sub")))
        if not user or user.get("role") not in ADMIN_ROLES:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
        return user
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")


def require_super_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return user
