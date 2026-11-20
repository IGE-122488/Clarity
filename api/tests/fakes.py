"""Supabase falso para testes: responde sem rede.

`SupabaseFalso` imita também a Data API (PostgREST) da tabela pacientes, incluindo o efeito das
regras RLS: cada token só vê os pacientes do seu psicólogo. As regras RLS verdadeiras são
testadas na base de dados com supabase/tests/pacientes_rls.sql.
"""

import json
import uuid
from datetime import UTC, datetime

import httpx

TOKEN_VALIDO = "token-valido"
TOKEN_OUTRA = "token-outra-psicologa"

PSICOLOGOS = {
    TOKEN_VALIDO: "uuid-psicologa-ficticia",
    TOKEN_OUTRA: "uuid-outra-psicologa",
}

COLUNAS_INSERT = {"nome", "data_nascimento"}
COLUNAS_UPDATE = {"nome", "data_nascimento", "ativo"}


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


class SupabaseFalso:
    """Auth + Data API em memória. Guarda os pedidos recebidos em `pedidos`."""

    def __init__(self) -> None:
        self.linhas: list[dict] = []
        self.pedidos: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request)
        if request.url.path != "/rest/v1/pacientes":
            return supabase_falso(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        dono = PSICOLOGOS.get(token)
        if dono is None:
            return httpx.Response(401, json={"code": "PGRST301", "message": "JWT invalid"})

        if request.method == "GET":
            return httpx.Response(200, json=self._ver(self._filtrar(request, dono)))
        if request.method == "POST":
            return self._criar(request, dono)
        if request.method == "PATCH":
            return self._alterar(request, dono)
        return httpx.Response(405)

    def _filtrar(self, request: httpx.Request, dono: str) -> list[dict]:
        params = request.url.params
        linhas = [linha for linha in self.linhas if linha["psicologo_id"] == dono]  # "RLS"
        if "id" in params:
            linhas = [linha for linha in linhas if f"eq.{linha['id']}" == params["id"]]
        if params.get("ativo") == "is.true":
            linhas = [linha for linha in linhas if linha["ativo"]]
        if params.get("order") == "nome.asc":
            linhas = sorted(linhas, key=lambda linha: linha["nome"])
        return linhas

    @staticmethod
    def _ver(linhas: list[dict]) -> list[dict]:
        return [{k: v for k, v in linha.items() if k != "psicologo_id"} for linha in linhas]

    def _criar(self, request: httpx.Request, dono: str) -> httpx.Response:
        dados = json.loads(request.content)
        if set(dados) - COLUNAS_INSERT:
            return httpx.Response(403, json={"code": "42501", "message": "permission denied"})
        agora = datetime.now(UTC).isoformat()
        linha = {
            "id": str(uuid.uuid4()),
            "psicologo_id": dono,
            "nome": dados["nome"],
            "data_nascimento": dados.get("data_nascimento"),
            "ativo": True,
            "criado_em": agora,
            "atualizado_em": agora,
        }
        self.linhas.append(linha)
        return httpx.Response(201, json=self._ver([linha]))

    def _alterar(self, request: httpx.Request, dono: str) -> httpx.Response:
        dados = json.loads(request.content)
        if set(dados) - COLUNAS_UPDATE:
            return httpx.Response(403, json={"code": "42501", "message": "permission denied"})
        linhas = self._filtrar(request, dono)
        for linha in linhas:
            linha.update(dados, atualizado_em=datetime.now(UTC).isoformat())
        return httpx.Response(200, json=self._ver(linhas))
