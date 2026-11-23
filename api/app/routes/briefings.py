"""Briefing pré-sessão gerado por IA, um por consulta.

- GET   /api/consultas/{id}/briefing → o briefing guardado, ou null se ainda não foi gerado.
- POST  /api/consultas/{id}/briefing → gera (ou gera de novo) a partir das notas das sessões
  anteriores do mesmo paciente. Fica sempre "por rever".
- PATCH /api/consultas/{id}/briefing → o psicólogo edita o texto e/ou marca como revisto.

Quem garante que cada psicólogo só vê os seus briefings é o Supabase (RLS): uma consulta de
outro psicólogo responde 404. À IA só vão datas e notas (ver app/briefing.py).
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from .. import supabase_db as db
from ..briefing import INSTRUCOES, montar_entrada, sessoes_anteriores
from ..config import Settings
from ..deps import ClientDep, SettingsDep, Token
from ..ia import RespostaIA, gerar_texto
from ..modelos import Briefing, BriefingAlteracao

router = APIRouter(prefix="/consultas", tags=["briefings"])

Gerador = Callable[..., Awaitable[RespostaIA]]


def get_gerador() -> Gerador:
    """Quem gera o texto. Nos testes é substituído por um gerador falso (sem rede nem custos)."""
    return gerar_texto


GeradorDep = Annotated[Gerador, Depends(get_gerador)]


async def _consulta(client: httpx.AsyncClient, settings: Settings, token: str, id_: UUID) -> dict:
    consulta = await db.obter_consulta(client, settings, token, id_)
    if consulta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consulta não encontrada.")
    return consulta


@router.get("/{consulta_id}/briefing", response_model=Briefing | None)
async def obter(
    consulta_id: UUID, settings: SettingsDep, client: ClientDep, token: Token
) -> dict | None:
    await _consulta(client, settings, token, consulta_id)
    return await db.obter_briefing(client, settings, token, consulta_id)


@router.post("/{consulta_id}/briefing", response_model=Briefing)
async def gerar(
    consulta_id: UUID,
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
    gerador: GeradorDep,
) -> dict:
    consulta = await _consulta(client, settings, token, consulta_id)
    if consulta["estado"] == "cancelada":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta consulta está cancelada.")

    inicio = datetime.fromisoformat(consulta["inicio"])
    anteriores = await db.sessoes_realizadas_antes(
        client, settings, token, UUID(consulta["paciente_id"]), inicio
    )
    sessoes = sessoes_anteriores(anteriores, inicio)
    if not sessoes:
        raise HTTPException(
            422,
            "Ainda não há sessões realizadas com notas antes desta consulta. "
            "Escreva as notas das sessões anteriores e marque-as como realizadas.",
        )

    entrada, usadas = montar_entrada(inicio, sessoes)
    resposta = await gerador(client, settings, instrucoes=INSTRUCOES, entrada=entrada)

    dados = {
        "texto": resposta.texto[:20000],
        "modelo": resposta.modelo[:100],
        "sessoes_usadas": usadas,
    }
    existente = await db.obter_briefing(client, settings, token, consulta_id)
    if existente is None:
        return await db.criar_briefing(
            client, settings, token, {**dados, "consulta_id": str(consulta_id)}
        )

    novo = {**dados, "revisto": False, "gerado_em": db.iso_utc(datetime.now(UTC))}
    briefing = await db.atualizar_briefing(client, settings, token, UUID(existente["id"]), novo)
    if briefing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Briefing não encontrado.")
    return briefing


@router.patch("/{consulta_id}/briefing", response_model=Briefing)
async def alterar(
    consulta_id: UUID,
    dados: BriefingAlteracao,
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
) -> dict:
    existente = await db.obter_briefing(client, settings, token, consulta_id)
    if existente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ainda não há briefing para esta consulta.")
    alteracoes = dados.model_dump(exclude_unset=True)
    briefing = await db.atualizar_briefing(
        client, settings, token, UUID(existente["id"]), alteracoes
    )
    if briefing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ainda não há briefing para esta consulta.")
    return briefing
