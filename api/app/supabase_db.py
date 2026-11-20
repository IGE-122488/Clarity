"""Acesso à base de dados (Data API / PostgREST do Supabase) em nome do psicólogo.

Cada pedido leva a chave publishable + o token do psicólogo. Assim é a base de dados (regras RLS)
que decide o que ele pode ver e alterar. Nunca usar aqui a secret key / service_role.

Os erros nunca incluem a resposta da base de dados: pode conter dados de pacientes.
"""

from typing import Any
from uuid import UUID

import httpx

from .config import Settings

COLUNAS_PACIENTE = "id,nome,data_nascimento,ativo,criado_em,atualizado_em"


class SessaoInvalida(Exception):
    """O Supabase recusou o token (inválido ou expirado)."""


class SemPermissao(Exception):
    """As permissões ou as regras RLS recusaram a operação."""


class ErroBaseDados(Exception):
    """Falha de rede ou erro inesperado da base de dados."""


def _cabecalhos(settings: Settings, token: str, **extra: str) -> dict[str, str]:
    return {
        "apikey": settings.supabase_publishable_key,
        "Authorization": f"Bearer {token}",
        **extra,
    }


async def _pedido(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> Any:
    try:
        res = await client.request(method, url, timeout=10.0, **kwargs)
    except httpx.HTTPError as exc:
        raise ErroBaseDados("Sem ligação à base de dados.") from exc

    if res.status_code == 401:
        raise SessaoInvalida("Sessão inválida ou expirada.")
    if res.status_code == 403:
        raise SemPermissao("Sem permissão para esta operação.")
    if res.status_code >= 400:
        raise ErroBaseDados(f"A base de dados respondeu com o código {res.status_code}.")
    return res.json()


def _url(settings: Settings) -> str:
    return f"{settings.supabase_url}/rest/v1/pacientes"


async def listar_pacientes(
    client: httpx.AsyncClient, settings: Settings, token: str, *, incluir_arquivados: bool = False
) -> list[dict]:
    params = {"select": COLUNAS_PACIENTE, "order": "nome.asc"}
    if not incluir_arquivados:
        params["ativo"] = "is.true"
    return await _pedido(
        client, "GET", _url(settings), params=params, headers=_cabecalhos(settings, token)
    )


async def obter_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID
) -> dict | None:
    linhas = await _pedido(
        client,
        "GET",
        _url(settings),
        params={"select": COLUNAS_PACIENTE, "id": f"eq.{paciente_id}"},
        headers=_cabecalhos(settings, token),
    )
    return linhas[0] if linhas else None


async def criar_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, dados: dict
) -> dict:
    linhas = await _pedido(
        client,
        "POST",
        _url(settings),
        params={"select": COLUNAS_PACIENTE},
        json=dados,
        headers=_cabecalhos(settings, token, Prefer="return=representation"),
    )
    return linhas[0]


async def atualizar_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID, dados: dict
) -> dict | None:
    """Devolve None se o paciente não existir ou for de outro psicólogo (o RLS esconde-o)."""
    linhas = await _pedido(
        client,
        "PATCH",
        _url(settings),
        params={"select": COLUNAS_PACIENTE, "id": f"eq.{paciente_id}"},
        json=dados,
        headers=_cabecalhos(settings, token, Prefer="return=representation"),
    )
    return linhas[0] if linhas else None
