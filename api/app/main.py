"""Ponto de entrada da API do Clarity.

No Vercel, todos os pedidos para /api/... chegam aqui (ver vercel.json na raiz).
Localmente: `uvicorn app.main:app --reload --port 8000` dentro da pasta api/.
"""

from fastapi import FastAPI

from .config import get_settings
from .routes import estado

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
