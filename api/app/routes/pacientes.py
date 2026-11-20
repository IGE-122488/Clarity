"""Pacientes do psicólogo com sessão iniciada.

A API não filtra por psicólogo: quem garante que cada um só vê os seus é o Supabase (RLS),
porque cada pedido vai com o token do próprio psicólogo.
Um paciente de outro psicólogo responde 404, como se não existisse.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .. import supabase_db as db
from ..deps import ClientDep, SettingsDep, Token
from ..modelos import Paciente, PacienteAlteracao, PacienteNovo

router = APIRouter(prefix="/pacientes", tags=["pacientes"])

NAO_ENCONTRADO = "Paciente não encontrado."


@router.get("", response_model=list[Paciente])
async def listar(
    settings: SettingsDep, client: ClientDep, token: Token, arquivados: bool = False
) -> list[dict]:
    """Lista os pacientes por ordem alfabética. `?arquivados=true` inclui os arquivados."""
    return await db.listar_pacientes(client, settings, token, incluir_arquivados=arquivados)


@router.post("", response_model=Paciente, status_code=status.HTTP_201_CREATED)
async def criar(
    dados: PacienteNovo, settings: SettingsDep, client: ClientDep, token: Token
) -> dict:
    return await db.criar_paciente(client, settings, token, dados.model_dump(mode="json"))


@router.get("/{paciente_id}", response_model=Paciente)
async def obter(paciente_id: UUID, settings: SettingsDep, client: ClientDep, token: Token) -> dict:
    paciente = await db.obter_paciente(client, settings, token, paciente_id)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    return paciente


@router.patch("/{paciente_id}", response_model=Paciente)
async def alterar(
    paciente_id: UUID,
    dados: PacienteAlteracao,
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
) -> dict:
    """Altera só os campos enviados. Para arquivar: `{"ativo": false}`."""
    alteracoes = dados.model_dump(mode="json", exclude_unset=True)
    paciente = await db.atualizar_paciente(client, settings, token, paciente_id, alteracoes)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    return paciente
