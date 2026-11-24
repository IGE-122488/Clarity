"""Ponto de entrada da API do Clarity.

No Vercel, todos os pedidos para /api/... chegam aqui (ver vercel.json na raiz).
Localmente: `uvicorn app.main:app --reload --port 8000` dentro da pasta api/.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .config import get_settings
from .ia import ErroIA, IANaoConfigurada
from .ocr import ErroOCR, OCRNaoConfigurado
from .routes import briefings, consultas, estado, ocr, pacientes
from .supabase_db import Conflito, ErroBaseDados, SemPermissao, SessaoInvalida

settings = get_settings()

app = FastAPI(
    title="Clarity API",
    version="0.1.0",
    # Documentação interativa só fora de produção.
    docs_url=None if settings.app_env == "production" else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.app_env == "production" else "/api/openapi.json",
)

app.include_router(estado.router, prefix="/api")
app.include_router(pacientes.router, prefix="/api")
app.include_router(consultas.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(ocr.router, prefix="/api")


# Erros da base de dados → respostas claras, sem detalhes internos (podem conter dados).
@app.exception_handler(SessaoInvalida)
async def _sessao_invalida(_request: Request, _exc: SessaoInvalida) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Sessão inválida ou expirada. Inicie sessão de novo."},
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.exception_handler(SemPermissao)
async def _sem_permissao(_request: Request, _exc: SemPermissao) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "Sem permissão para esta operação."},
    )


@app.exception_handler(ErroBaseDados)
async def _erro_base_dados(_request: Request, _exc: ErroBaseDados) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "Não foi possível contactar a base de dados. Tente de novo."},
    )


@app.exception_handler(Conflito)
async def _conflito(_request: Request, _exc: Conflito) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "Os dados não respeitam as regras (por exemplo, paciente de outro psicólogo)."
        },
    )


@app.exception_handler(IANaoConfigurada)
async def _ia_nao_configurada(_request: Request, _exc: IANaoConfigurada) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "O briefing por IA ainda não está configurado neste ambiente."},
    )


@app.exception_handler(ErroIA)
async def _erro_ia(_request: Request, exc: ErroIA) -> JSONResponse:
    # A mensagem foi escrita por nós em app/ia.py: nunca contém notas nem respostas do Azure.
    return JSONResponse(status_code=exc.codigo, content={"detail": str(exc)})


@app.exception_handler(OCRNaoConfigurado)
async def _ocr_nao_configurado(_request: Request, _exc: OCRNaoConfigurado) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "A digitalização de notas ainda não está configurada neste ambiente."},
    )


@app.exception_handler(ErroOCR)
async def _erro_ocr(_request: Request, exc: ErroOCR) -> JSONResponse:
    # A mensagem foi escrita por nós em app/ocr.py: nunca contém a imagem nem o texto lido.
    return JSONResponse(status_code=exc.codigo, content={"detail": str(exc)})
