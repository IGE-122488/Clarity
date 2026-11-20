"""Configuração lida das variáveis de ambiente.

Falha cedo, com uma mensagem clara, se faltar alguma variável obrigatória.
"""

import os
from dataclasses import dataclass
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
    return Settings(url, key, app_env, commit)


@lru_cache
def get_settings() -> Settings:
    return read_settings()
