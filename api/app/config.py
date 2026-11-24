"""Configuração lida das variáveis de ambiente.

Falha cedo, com uma mensagem clara, se faltar alguma variável obrigatória.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache

APP_ENVS = ("development", "preview", "production")


class ConfigError(RuntimeError):
    """Configuração em falta ou inválida."""


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    app_env: str
    commit: str | None = None
    # IA (Azure OpenAI). Opcional: sem estas variáveis, só o briefing fica indisponível (503).
    ia_base_url: str | None = None
    ia_api_key: str | None = field(default=None, repr=False)  # nunca aparecer em registos
    ia_deployment: str | None = None
    # OCR (Azure Document Intelligence). Opcional: sem isto, só a digitalização fica indisponível.
    ocr_endpoint: str | None = None
    ocr_key: str | None = field(default=None, repr=False)  # nunca aparecer em registos

    @property
    def ia_configurada(self) -> bool:
        return bool(self.ia_base_url and self.ia_api_key and self.ia_deployment)

    @property
    def ocr_configurado(self) -> bool:
        return bool(self.ocr_endpoint and self.ocr_key)


def read_settings(env: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ) if env is None else env

    url = env.get("SUPABASE_URL", "").strip().rstrip("/")
    key = env.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    app_env = env.get("APP_ENV", "").strip() or "development"

    missing = [
        name
        for name, value in (("SUPABASE_URL", url), ("SUPABASE_PUBLISHABLE_KEY", key))
        if not value
    ]
    if missing:
        raise ConfigError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Copiem api/.env.example para api/.env e preencham-nas."
        )
    if app_env not in APP_ENVS:
        raise ConfigError(f'APP_ENV inválido: "{app_env}". Use {", ".join(APP_ENVS)}.')

    commit = env.get("VERCEL_GIT_COMMIT_SHA", "")[:7] or None

    # Aceita o endereço com ou sem "/responses" no fim (é o que o portal do Azure mostra).
    ia_base_url = env.get("AZURE_OPENAI_BASE_URL", "").strip().rstrip("/")
    ia_base_url = ia_base_url.removesuffix("/responses").rstrip("/")
    if not ia_base_url.startswith("https://"):
        ia_base_url = (
            ""  # endereço inválido = IA não configurada (o resto da API continua a funcionar)
        )

    ocr_endpoint = env.get("AZURE_DOCINTEL_ENDPOINT", "").strip().rstrip("/")
    if not ocr_endpoint.startswith("https://"):
        ocr_endpoint = ""  # endereço inválido = OCR não configurado

    return Settings(
        url,
        key,
        app_env,
        commit,
        ia_base_url=ia_base_url or None,
        ia_api_key=env.get("AZURE_OPENAI_API_KEY", "").strip() or None,
        ia_deployment=env.get("AZURE_OPENAI_DEPLOYMENT", "").strip() or None,
        ocr_endpoint=ocr_endpoint or None,
        ocr_key=env.get("AZURE_DOCINTEL_KEY", "").strip() or None,
    )


@lru_cache
def get_settings() -> Settings:
    return read_settings()
