"""Dependências partilhadas pelos endpoints."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings
from .supabase_auth import InvalidToken, User, get_user


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


SettingsDep = Annotated[Settings, Depends(get_settings)]
ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="É necessário iniciar sessão.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


# Token do psicólogo, passado tal e qual ao Supabase (que o valida e aplica as regras RLS).
Token = Annotated[str, Depends(bearer_token)]


async def current_user(
    settings: SettingsDep,
    client: ClientDep,
    token: Annotated[str, Depends(bearer_token)],
) -> User:
    try:
        return await get_user(client, settings, token)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[User, Depends(current_user)]
