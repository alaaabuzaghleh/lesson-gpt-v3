from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from remote_lessons_gpt.api.auth_utils import ADMIN_ROLES

from extractor_lessons_gpt.api.remote_client import RemoteApiError, RemoteIngestClient, remote_api_configured

_bearer = HTTPBearer(auto_error=False)


def _validate_remote_user(token: str) -> dict:
    if not remote_api_configured():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "REMOTE_API_URL is not configured on the extractor",
        )
    try:
        return RemoteIngestClient(token).me()
    except RemoteApiError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return _validate_remote_user(creds.credentials)


def require_admin(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_admin_sse(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    token: Annotated[str | None, Query()] = None,
) -> dict:
    auth_token = creds.credentials if creds and creds.credentials else token
    if not auth_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    user = _validate_remote_user(auth_token)
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
