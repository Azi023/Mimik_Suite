"""Auth dependency: turn a Bearer token into a Principal whose tenant_id scopes every query."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .security import decode_access_token

_bearer = HTTPBearer(auto_error=True)


class Principal(BaseModel):
    tenant_id: str
    role: str


def get_principal(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Principal:
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    tenant_id = payload.get("sub")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")
    return Principal(tenant_id=tenant_id, role=payload.get("role", "team"))
