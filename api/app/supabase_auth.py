"""Chamadas ao Supabase Auth.

Não lê nem escreve dados clínicos: só verifica a ligação e quem é o utilizador.
"""

from dataclasses import dataclass

import httpx

from .config import Settings


class InvalidToken(Exception):
    """Token em falta, inválido ou expirado."""


@dataclass(frozen=True)
class User:
    id: str
    email: str | None


async def check_health(client: httpx.AsyncClient, settings: Settings) -> bool:
    """True se o Supabase Auth responder."""
    try:
        res = await client.get(
            f"{settings.supabase_url}/auth/v1/health",
            headers={"apikey": settings.supabase_publishable_key},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return False
    return res.status_code == 200


async def get_user(client: httpx.AsyncClient, settings: Settings, token: str) -> User:
    """Valida o token do psicólogo junto do Supabase e devolve o utilizador.

    Passo seguinte (otimização): validar o JWT localmente com as chaves públicas (JWKS)
    do projeto, para evitar um pedido de rede em cada chamada.
    """
    try:
        res = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise InvalidToken("Não foi possível validar a sessão.") from exc

    if res.status_code != 200:
        raise InvalidToken("Sessão inválida ou expirada.")

    data = res.json()
    return User(id=data["id"], email=data.get("email"))
