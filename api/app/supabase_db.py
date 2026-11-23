"""Acesso à base de dados (Data API / PostgREST do Supabase) em nome do psicólogo.

Cada pedido leva a chave publishable + o token do psicólogo. Assim é a base de dados (regras RLS)
que decide o que ele pode ver e alterar. Nunca usar aqui a secret key / service_role.

Os erros nunca incluem a resposta da base de dados: pode conter dados de pacientes.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from .config import Settings

COLUNAS_PACIENTE = "id,nome,data_nascimento,ativo,criado_em,atualizado_em"
# Na agenda não vêm as notas (minimização): só ao abrir a consulta ou o histórico do paciente.
COLUNAS_CONSULTA_AGENDA = "id,paciente_id,inicio,fim,estado,criado_em,atualizado_em"
COLUNAS_CONSULTA = COLUNAS_CONSULTA_AGENDA + ",notas"


class SessaoInvalida(Exception):
    """O Supabase recusou o token (inválido ou expirado)."""


class SemPermissao(Exception):
    """As permissões ou as regras RLS recusaram a operação."""


class ErroBaseDados(Exception):
    """Falha de rede ou erro inesperado da base de dados."""


class Conflito(Exception):
    """A base de dados recusou os dados por violarem uma regra (ex.: paciente de outro dono)."""


def iso_utc(momento: datetime) -> str:
    """Data/hora em UTC, sempre no mesmo formato (ex.: 2026-12-01T10:00:00Z)."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    if res.status_code == 409:
        raise Conflito("Os dados não respeitam as regras da base de dados.")
    if res.status_code >= 400:
        raise ErroBaseDados(f"A base de dados respondeu com o código {res.status_code}.")
    return res.json()


def _url(settings: Settings, tabela: str) -> str:
    return f"{settings.supabase_url}/rest/v1/{tabela}"


async def _listar(
    client: httpx.AsyncClient, settings: Settings, token: str, tabela: str, params: dict
) -> list[dict]:
    return await _pedido(
        client, "GET", _url(settings, tabela), params=params, headers=_cabecalhos(settings, token)
    )


async def _obter(
    client: httpx.AsyncClient, settings: Settings, token: str, tabela: str, colunas: str, id_: UUID
) -> dict | None:
    linhas = await _listar(client, settings, token, tabela, {"select": colunas, "id": f"eq.{id_}"})
    return linhas[0] if linhas else None


async def _criar(
    client: httpx.AsyncClient,
    settings: Settings,
    token: str,
    tabela: str,
    colunas: str,
    dados: dict,
) -> dict:
    linhas = await _pedido(
        client,
        "POST",
        _url(settings, tabela),
        params={"select": colunas},
        json=dados,
        headers=_cabecalhos(settings, token, Prefer="return=representation"),
    )
    return linhas[0]


async def _atualizar(
    client: httpx.AsyncClient,
    settings: Settings,
    token: str,
    tabela: str,
    colunas: str,
    id_: UUID,
    dados: dict,
) -> dict | None:
    """Devolve None se a linha não existir ou for de outro psicólogo (o RLS esconde-a)."""
    linhas = await _pedido(
        client,
        "PATCH",
        _url(settings, tabela),
        params={"select": colunas, "id": f"eq.{id_}"},
        json=dados,
        headers=_cabecalhos(settings, token, Prefer="return=representation"),
    )
    return linhas[0] if linhas else None


# Pacientes


async def listar_pacientes(
    client: httpx.AsyncClient, settings: Settings, token: str, *, incluir_arquivados: bool = False
) -> list[dict]:
    params = {"select": COLUNAS_PACIENTE, "order": "nome.asc"}
    if not incluir_arquivados:
        params["ativo"] = "is.true"
    return await _listar(client, settings, token, "pacientes", params)


async def obter_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID
) -> dict | None:
    return await _obter(client, settings, token, "pacientes", COLUNAS_PACIENTE, paciente_id)


async def criar_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, dados: dict
) -> dict:
    return await _criar(client, settings, token, "pacientes", COLUNAS_PACIENTE, dados)


async def atualizar_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID, dados: dict
) -> dict | None:
    return await _atualizar(
        client, settings, token, "pacientes", COLUNAS_PACIENTE, paciente_id, dados
    )


# Consultas (agenda)


async def listar_consultas(
    client: httpx.AsyncClient, settings: Settings, token: str, *, de: datetime, ate: datetime
) -> list[dict]:
    """Consultas que se cruzam com o intervalo [de, ate[, por ordem de início. Sem notas."""
    params = {
        "select": COLUNAS_CONSULTA_AGENDA,
        "inicio": f"lt.{iso_utc(ate)}",
        "fim": f"gt.{iso_utc(de)}",
        "order": "inicio.asc",
    }
    return await _listar(client, settings, token, "consultas", params)


async def listar_consultas_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID
) -> list[dict]:
    """Histórico e próximas consultas de um paciente, das mais recentes para as mais antigas."""
    params = {
        "select": COLUNAS_CONSULTA,
        "paciente_id": f"eq.{paciente_id}",
        "order": "inicio.desc",
        "limit": "500",
    }
    return await _listar(client, settings, token, "consultas", params)


async def consultas_sobrepostas(
    client: httpx.AsyncClient,
    settings: Settings,
    token: str,
    *,
    inicio: datetime,
    fim: datetime,
    excluir_id: UUID | None = None,
) -> list[dict]:
    """Consultas não canceladas do psicólogo que se cruzam com [inicio, fim[."""
    params = {
        "select": COLUNAS_CONSULTA_AGENDA,
        "inicio": f"lt.{iso_utc(fim)}",
        "fim": f"gt.{iso_utc(inicio)}",
        "estado": "neq.cancelada",
        "order": "inicio.asc",
    }
    if excluir_id is not None:
        params["id"] = f"neq.{excluir_id}"
    return await _listar(client, settings, token, "consultas", params)


async def obter_consulta(
    client: httpx.AsyncClient, settings: Settings, token: str, consulta_id: UUID
) -> dict | None:
    return await _obter(client, settings, token, "consultas", COLUNAS_CONSULTA, consulta_id)


async def criar_consulta(
    client: httpx.AsyncClient, settings: Settings, token: str, dados: dict
) -> dict:
    return await _criar(client, settings, token, "consultas", COLUNAS_CONSULTA, dados)


async def atualizar_consulta(
    client: httpx.AsyncClient, settings: Settings, token: str, consulta_id: UUID, dados: dict
) -> dict | None:
    return await _atualizar(
        client, settings, token, "consultas", COLUNAS_CONSULTA, consulta_id, dados
    )
