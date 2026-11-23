"""Supabase falso para testes: responde sem rede.

`SupabaseFalso` imita também a Data API (PostgREST) das tabelas pacientes e consultas, incluindo
o efeito das regras RLS (cada token só vê as linhas do seu psicólogo), das permissões por coluna
e da chave estrangeira que obriga a consulta a ser de um paciente do mesmo psicólogo.
As regras verdadeiras são testadas na base de dados com supabase/tests/*.sql.
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

TABELAS = {
    "pacientes": {
        "insert": {"nome", "data_nascimento"},
        "update": {"nome", "data_nascimento", "ativo"},
        "omissao": {"data_nascimento": None, "ativo": True},
    },
    "consultas": {
        "insert": {"paciente_id", "inicio", "fim", "estado", "notas"},
        "update": {"inicio", "fim", "estado", "notas"},
        "omissao": {"estado": "agendada", "notas": None},
    },
}

PARAMETROS_ESPECIAIS = {"select", "order", "limit"}


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


def _agora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cumpre(linha: dict, coluna: str, condicao: str) -> bool:
    operador, valor = condicao.split(".", 1)
    atual = linha.get(coluna)
    if operador == "is":
        return atual is {"true": True, "false": False, "null": None}[valor]
    if atual is None:
        return False
    atual = str(atual)
    return {
        "eq": atual == valor,
        "neq": atual != valor,
        "lt": atual < valor,
        "gt": atual > valor,
        "lte": atual <= valor,
        "gte": atual >= valor,
    }[operador]


class SupabaseFalso:
    """Auth + Data API em memória. Guarda os pedidos recebidos em `pedidos`."""

    def __init__(self) -> None:
        self.tabelas: dict[str, list[dict]] = {nome: [] for nome in TABELAS}
        self.pedidos: list[httpx.Request] = []

    # Compatibilidade com os testes do passo 2
    @property
    def linhas(self) -> list[dict]:
        return self.tabelas["pacientes"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request)
        prefixo = "/rest/v1/"
        tabela = request.url.path.removeprefix(prefixo)
        if not request.url.path.startswith(prefixo) or tabela not in TABELAS:
            return supabase_falso(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        dono = PSICOLOGOS.get(token)
        if dono is None:
            return httpx.Response(401, json={"code": "PGRST301", "message": "JWT invalid"})

        if request.method == "GET":
            return httpx.Response(
                200, json=self._ver(request, self._filtrar(request, tabela, dono))
            )
        if request.method == "POST":
            return self._criar(request, tabela, dono)
        if request.method == "PATCH":
            return self._alterar(request, tabela, dono)
        return httpx.Response(405)

    def _filtrar(self, request: httpx.Request, tabela: str, dono: str) -> list[dict]:
        params = request.url.params
        linhas = [linha for linha in self.tabelas[tabela] if linha["psicologo_id"] == dono]  # RLS
        for coluna, condicao in params.multi_items():
            if coluna not in PARAMETROS_ESPECIAIS:
                linhas = [linha for linha in linhas if _cumpre(linha, coluna, condicao)]
        if "order" in params:
            coluna, sentido = params["order"].split(".")
            linhas = sorted(linhas, key=lambda linha: str(linha[coluna]), reverse=sentido == "desc")
        if "limit" in params:
            linhas = linhas[: int(params["limit"])]
        return linhas

    @staticmethod
    def _ver(request: httpx.Request, linhas: list[dict]) -> list[dict]:
        colunas = request.url.params.get("select", "*").split(",")
        return [
            {
                k: v
                for k, v in linha.items()
                if k != "psicologo_id" and (k in colunas or colunas == ["*"])
            }
            for linha in linhas
        ]

    def _violacoes(self, tabela: str, linha: dict, dono: str) -> httpx.Response | None:
        if tabela != "consultas":
            return None
        paciente = next(
            (
                p
                for p in self.tabelas["pacientes"]
                if p["id"] == linha["paciente_id"] and p["psicologo_id"] == dono
            ),
            None,
        )
        if paciente is None:  # chave estrangeira (paciente_id, psicologo_id)
            return httpx.Response(409, json={"code": "23503", "message": "foreign key violation"})
        if not linha["fim"] > linha["inicio"]:
            return httpx.Response(400, json={"code": "23514", "message": "check violation"})
        return None

    def _criar(self, request: httpx.Request, tabela: str, dono: str) -> httpx.Response:
        dados = json.loads(request.content)
        if set(dados) - TABELAS[tabela]["insert"]:
            return httpx.Response(403, json={"code": "42501", "message": "permission denied"})
        agora = _agora()
        linha = {
            **TABELAS[tabela]["omissao"],
            **dados,
            "id": str(uuid.uuid4()),
            "psicologo_id": dono,
            "criado_em": agora,
            "atualizado_em": agora,
        }
        if (erro := self._violacoes(tabela, linha, dono)) is not None:
            return erro
        self.tabelas[tabela].append(linha)
        return httpx.Response(201, json=self._ver(request, [linha]))

    def _alterar(self, request: httpx.Request, tabela: str, dono: str) -> httpx.Response:
        dados = json.loads(request.content)
        if set(dados) - TABELAS[tabela]["update"]:
            return httpx.Response(403, json={"code": "42501", "message": "permission denied"})
        linhas = self._filtrar(request, tabela, dono)
        for linha in linhas:
            if (erro := self._violacoes(tabela, {**linha, **dados}, dono)) is not None:
                return erro
        for linha in linhas:
            linha.update(dados, atualizado_em=_agora())
        return httpx.Response(200, json=self._ver(request, linhas))
