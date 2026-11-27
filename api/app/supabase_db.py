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
COLUNAS_BRIEFING = (
    "id,consulta_id,texto,revisto,modelo,sessoes_usadas,gerado_em,criado_em,atualizado_em"
)


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


async def apagar_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID
) -> bool:
    """Apaga o paciente e, em cascata na base de dados, as consultas, notas e briefings dele.

    Devolve False se o paciente não existir ou for de outro psicólogo (o RLS esconde-o)."""
    linhas = await _pedido(
        client,
        "DELETE",
        _url(settings, "pacientes"),
        params={"select": "id", "id": f"eq.{paciente_id}"},
        headers=_cabecalhos(settings, token, Prefer="return=representation"),
    )
    return bool(linhas)


# Exportação (RGPD)

PAGINA = 1000  # o Supabase devolve no máximo 1000 linhas por pedido
LOTE_IDS = 100  # ids por pedido "in.(...)", para o URL não ficar demasiado comprido


async def _listar_tudo(
    client: httpx.AsyncClient, settings: Settings, token: str, tabela: str, params: dict
) -> list[dict]:
    """Todas as linhas, página a página (params tem de ter um "order" sem empates)."""
    linhas: list[dict] = []
    while True:
        pagina = await _listar(
            client,
            settings,
            token,
            tabela,
            {**params, "limit": str(PAGINA), "offset": str(len(linhas))},
        )
        linhas += pagina
        if len(pagina) < PAGINA:
            return linhas


async def dados_do_paciente(
    client: httpx.AsyncClient, settings: Settings, token: str, paciente_id: UUID
) -> tuple[list[dict], list[dict]]:
    """Todas as consultas do paciente (mais antigas primeiro) e todos os briefings delas."""
    consultas = await _listar_tudo(
        client,
        settings,
        token,
        "consultas",
        {
            "select": COLUNAS_CONSULTA,
            "paciente_id": f"eq.{paciente_id}",
            "order": "inicio.asc,id.asc",
        },
    )
    ids = [c["id"] for c in consultas]
    briefings: list[dict] = []
    for i in range(0, len(ids), LOTE_IDS):
        lote = ",".join(ids[i : i + LOTE_IDS])
        briefings += await _listar(
            client,
            settings,
            token,
            "briefings",
            {"select": COLUNAS_BRIEFING, "consulta_id": f"in.({lote})"},
        )
    return consultas, briefings


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


async def sessoes_realizadas_antes(
    client: httpx.AsyncClient,
    settings: Settings,
    token: str,
    paciente_id: UUID,
    antes_de: datetime,
    limite: int = 20,
) -> list[dict]:
    """Sessões realizadas do paciente antes de uma data, com notas, das mais recentes primeiro."""
    params = {
        "select": COLUNAS_CONSULTA,
        "paciente_id": f"eq.{paciente_id}",
        "estado": "eq.realizada",
        "inicio": f"lt.{iso_utc(antes_de)}",
        "order": "inicio.desc",
        "limit": str(limite),
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


# Briefings (um por consulta)


async def obter_briefing(
    client: httpx.AsyncClient, settings: Settings, token: str, consulta_id: UUID
) -> dict | None:
    linhas = await _listar(
        client,
        settings,
        token,
        "briefings",
        {"select": COLUNAS_BRIEFING, "consulta_id": f"eq.{consulta_id}"},
    )
    return linhas[0] if linhas else None


async def criar_briefing(
    client: httpx.AsyncClient, settings: Settings, token: str, dados: dict
) -> dict:
    return await _criar(client, settings, token, "briefings", COLUNAS_BRIEFING, dados)


async def atualizar_briefing(
    client: httpx.AsyncClient, settings: Settings, token: str, briefing_id: UUID, dados: dict
) -> dict | None:
    return await _atualizar(
        client, settings, token, "briefings", COLUNAS_BRIEFING, briefing_id, dados
    )
