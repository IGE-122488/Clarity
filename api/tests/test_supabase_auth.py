import asyncio

import httpx
import pytest

from app.config import read_settings
from app.supabase_auth import InvalidToken, check_health, get_user
from tests.fakes import TOKEN_VALIDO, supabase_em_baixo, supabase_falso

SETTINGS = read_settings(
    {"SUPABASE_URL": "https://exemplo.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x"}
)


def run(coro_factory, handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_factory(client)

    return asyncio.run(go())


def test_health_ligado():
    assert run(lambda c: check_health(c, SETTINGS), supabase_falso) is True


def test_health_sem_rede():
    assert run(lambda c: check_health(c, SETTINGS), supabase_em_baixo) is False


def test_get_user_token_valido():
    user = run(lambda c: get_user(c, SETTINGS, TOKEN_VALIDO), supabase_falso)
    assert user.id == "uuid-psicologa-ficticia"
    assert user.email == "ana@exemplo.pt"


def test_get_user_token_invalido():
    with pytest.raises(InvalidToken):
        run(lambda c: get_user(c, SETTINGS, "token-falso"), supabase_falso)


def test_get_user_sem_rede():
    with pytest.raises(InvalidToken):
        run(lambda c: get_user(c, SETTINGS, TOKEN_VALIDO), supabase_em_baixo)
