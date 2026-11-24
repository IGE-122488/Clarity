"""Importar notas: a app envia uma fotografia, um PDF ou um .docx e recebe o texto para rever.

POST /api/ocr/notas  — corpo: o ficheiro em bruto, com o Content-Type certo
(image/jpeg, image/png, application/pdf ou o tipo do .docx). Os .txt são lidos no browser.

Nada fica guardado aqui: o texto volta para o psicólogo, que o revê e corrige antes de o
acrescentar às notas da consulta. Exige sessão iniciada (para ninguém gastar a nossa quota).
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..deps import ClientDep, CurrentUser, SettingsDep
from ..modelos import TextoLido
from ..ocr import TAMANHO_MAXIMO, TIPOS_ACEITES, ler_texto

router = APIRouter(prefix="/ocr", tags=["ocr"])

Leitor = Callable[..., Awaitable[str]]


def get_leitor() -> Leitor:
    """Quem lê a imagem. Nos testes é substituído por um leitor falso (sem rede nem custos)."""
    return ler_texto


LeitorDep = Annotated[Leitor, Depends(get_leitor)]


@router.post("/notas", response_model=TextoLido)
async def digitalizar(
    request: Request,
    _utilizador: CurrentUser,
    settings: SettingsDep,
    client: ClientDep,
    leitor: LeitorDep,
) -> dict:
    tipo = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if tipo not in TIPOS_ACEITES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Envie uma fotografia (JPG ou PNG), um PDF ou um documento Word (.docx).",
        )

    demasiado_grande = HTTPException(413, "O ficheiro é demasiado grande (máximo 4 MB).")
    if int(request.headers.get("content-length") or 0) > TAMANHO_MAXIMO:
        raise demasiado_grande
    imagem = await request.body()
    if len(imagem) > TAMANHO_MAXIMO:
        raise demasiado_grande
    if not imagem:
        raise HTTPException(422, "O ficheiro está vazio.")

    texto = await leitor(client, settings, imagem, tipo)
    if not texto:
        raise HTTPException(422, "Não foi encontrado texto neste ficheiro.")
    return {"texto": texto[:20000]}
