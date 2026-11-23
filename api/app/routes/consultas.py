"""Agenda do psicólogo com sessão iniciada: consultas e notas de cada consulta.

Como nos pacientes, quem garante que cada psicólogo só vê as suas consultas é o Supabase (RLS).
Uma consulta de outro psicólogo responde 404, como se não existisse.

Sobreposição de horários: por omissão, marcar ou remarcar para um horário já ocupado responde 409
com a lista das consultas em conflito. A app mostra o aviso e, se o psicólogo confirmar, repete o
pedido com `ignorar_sobreposicao: true`.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .. import supabase_db as db
from ..deps import ClientDep, SettingsDep, Token
from ..modelos import Consulta, ConsultaAgenda, ConsultaAlteracao, ConsultaNova, validar_horario

router = APIRouter(prefix="/consultas", tags=["consultas"])

NAO_ENCONTRADA = "Consulta não encontrada."
INTERVALO_MAXIMO = timedelta(days=62)


def _erro(codigo: int, mensagem: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=mensagem)


def _com_fuso(momento: datetime, nome: str) -> datetime:
    if momento.tzinfo is None:
        raise _erro(
            422,
            f"'{nome}' tem de incluir o fuso horário (ex.: 2026-12-01T09:00:00Z).",
        )
    return momento


async def _verificar_sobreposicao(
    client, settings, token, inicio: datetime, fim: datetime, excluir_id: UUID | None = None
) -> None:
    sobrepostas = await db.consultas_sobrepostas(
        client, settings, token, inicio=inicio, fim=fim, excluir_id=excluir_id
    )
    if sobrepostas:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "mensagem": "Já tem outra consulta marcada neste horário.",
                "sobrepostas": [
                    ConsultaAgenda.model_validate(c).model_dump(mode="json") for c in sobrepostas
                ],
            },
        )


@router.get("", response_model=list[ConsultaAgenda])
async def listar(
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
    de: Annotated[datetime, Query(description="Início do intervalo, com fuso horário")],
    ate: Annotated[datetime, Query(description="Fim do intervalo, com fuso horário")],
) -> list[dict]:
    """Consultas que se cruzam com [de, ate[ (por exemplo, uma semana). Não inclui as notas."""
    de, ate = _com_fuso(de, "de"), _com_fuso(ate, "ate")
    if ate <= de:
        raise _erro(422, "'ate' tem de ser depois de 'de'.")
    if ate - de > INTERVALO_MAXIMO:
        raise _erro(422, "O intervalo máximo é de 62 dias.")
    return await db.listar_consultas(client, settings, token, de=de, ate=ate)


@router.post("", response_model=Consulta, status_code=status.HTTP_201_CREATED)
async def marcar(
    dados: ConsultaNova, settings: SettingsDep, client: ClientDep, token: Token
) -> dict:
    paciente = await db.obter_paciente(client, settings, token, dados.paciente_id)
    if paciente is None:
        raise _erro(status.HTTP_404_NOT_FOUND, "Paciente não encontrado.")
    if not paciente["ativo"]:
        raise _erro(status.HTTP_409_CONFLICT, "O paciente está arquivado. Reative-o primeiro.")

    if dados.estado != "cancelada" and not dados.ignorar_sobreposicao:
        await _verificar_sobreposicao(client, settings, token, dados.inicio, dados.fim)

    novo = dados.model_dump(mode="json", exclude={"ignorar_sobreposicao"})
    novo["inicio"], novo["fim"] = db.iso_utc(dados.inicio), db.iso_utc(dados.fim)
    return await db.criar_consulta(client, settings, token, novo)


@router.get("/{consulta_id}", response_model=Consulta)
async def obter(consulta_id: UUID, settings: SettingsDep, client: ClientDep, token: Token) -> dict:
    consulta = await db.obter_consulta(client, settings, token, consulta_id)
    if consulta is None:
        raise _erro(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADA)
    return consulta


@router.patch("/{consulta_id}", response_model=Consulta)
async def alterar(
    consulta_id: UUID,
    dados: ConsultaAlteracao,
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
) -> dict:
    """Altera só os campos enviados: remarcar (inicio/fim), estado (ex.: cancelada) ou notas."""
    atual = await db.obter_consulta(client, settings, token, consulta_id)
    if atual is None:
        raise _erro(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADA)

    alteracoes = dados.model_dump(mode="json", exclude_unset=True, exclude={"ignorar_sobreposicao"})
    inicio = dados.inicio or datetime.fromisoformat(atual["inicio"])
    fim = dados.fim or datetime.fromisoformat(atual["fim"])
    estado = dados.estado or atual["estado"]

    if "inicio" in alteracoes or "fim" in alteracoes:
        try:
            validar_horario(inicio, fim)
        except ValueError as exc:
            raise _erro(422, str(exc)) from exc
        alteracoes.update(inicio=db.iso_utc(inicio), fim=db.iso_utc(fim))

    muda_horario = "inicio" in alteracoes or "fim" in alteracoes
    volta_a_ficar_ativa = atual["estado"] == "cancelada" and estado != "cancelada"
    if (muda_horario or volta_a_ficar_ativa) and estado != "cancelada":
        if not dados.ignorar_sobreposicao:
            await _verificar_sobreposicao(client, settings, token, inicio, fim, consulta_id)

    consulta = await db.atualizar_consulta(client, settings, token, consulta_id, alteracoes)
    if consulta is None:
        raise _erro(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADA)
    return consulta
