"""Supabase falso para testes: responde sem rede."""

import httpx

TOKEN_VALIDO = "token-valido"


def supabase_falso(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/v1/health":
        return httpx.Response(200, json={"name": "GoTrue"})
    if request.url.path == "/auth/v1/user":
        if request.headers.get("Authorization") == f"Bearer {TOKEN_VALIDO}":
            return httpx.Response(
                200, json={"id": "uuid-psicologa-ficticia", "email": "ana@exemplo.pt"}
            )
        return httpx.Response(401, json={"msg": "invalid JWT"})
    return httpx.Response(404)


def supabase_em_baixo(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("sem rede", request=request)
