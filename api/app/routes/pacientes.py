"""Pacientes do psicólogo com sessão iniciada.

A API não filtra por psicólogo: quem garante que cada um só vê os seus é o Supabase (RLS),
porque cada pedido vai com o token do próprio psicólogo.
Um paciente de outro psicólogo responde 404, como se não existisse.

Passo 7 (RGPD): exportar todos os dados de um paciente e apagá-lo definitivamente.
"""

import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from .. import supabase_db as db
from ..deps import ClientDep, SettingsDep, Token
from ..modelos import ConfirmacaoApagar, Consulta, Paciente, PacienteAlteracao, PacienteNovo

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


@router.get("/{paciente_id}/consultas", response_model=list[Consulta])
async def consultas_do_paciente(
    paciente_id: UUID, settings: SettingsDep, client: ClientDep, token: Token
) -> list[dict]:
    """Histórico e próximas consultas do paciente (mais recentes primeiro), com as notas."""
    if await db.obter_paciente(client, settings, token, paciente_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    return await db.listar_consultas_paciente(client, settings, token, paciente_id)


# Passo 7 — RGPD


def _normalizar_nome(nome: str) -> str:
    """Compara nomes sem ligar a maiúsculas nem a espaços a mais (os acentos contam)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", nome)).strip().casefold()


@router.get("/{paciente_id}/exportar")
async def exportar(
    paciente_id: UUID, settings: SettingsDep, client: ClientDep, token: Token
) -> JSONResponse:
    """Todos os dados do paciente num JSON (direito de acesso e portabilidade, RGPD art. 15 e 20):
    a ficha, todas as consultas com as notas e os briefings."""
    paciente = await db.obter_paciente(client, settings, token, paciente_id)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    consultas, briefings = await db.dados_do_paciente(client, settings, token, paciente_id)
    por_consulta = {b["consulta_id"]: b for b in briefings}

    agora = datetime.now(UTC)
    conteudo = {
        "formato": "clarity.exportacao-paciente",
        "versao": 1,
        "exportado_em": db.iso_utc(agora),
        "paciente": paciente,
        "consultas": [
            {
                **{k: v for k, v in c.items() if k != "paciente_id"},
                "briefing": (
                    {k: v for k, v in b.items() if k != "consulta_id"}
                    if (b := por_consulta.get(c["id"]))
                    else None
                ),
            }
            for c in consultas
        ],
    }
    nome_ficheiro = f"clarity-paciente-{agora:%Y-%m-%d}.json"
    return JSONResponse(
        conteudo,
        headers={
            "Content-Disposition": f'attachment; filename="{nome_ficheiro}"',
            "Cache-Control": "no-store",  # dados de saúde: nunca em cache
        },
    )


@router.delete("/{paciente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def apagar(
    paciente_id: UUID,
    dados: ConfirmacaoApagar,
    settings: SettingsDep,
    client: ClientDep,
    token: Token,
) -> Response:
    """Apaga definitivamente o paciente, as consultas, as notas e os briefings (RGPD art. 17).

    Não se pode desfazer. Para confirmar, o corpo traz o nome do paciente escrito pelo psicólogo."""
    paciente = await db.obter_paciente(client, settings, token, paciente_id)
    if paciente is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    if _normalizar_nome(dados.confirmacao) != _normalizar_nome(paciente["nome"]):
        raise HTTPException(
            status_code=422,
            detail="O nome escrito não coincide com o nome do paciente. Nada foi apagado.",
        )
    if not await db.apagar_paciente(client, settings, token, paciente_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NAO_ENCONTRADO)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
