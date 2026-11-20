import httpx
import pytest
from fastapi.testclient import TestClient

from app.deps import get_http_client
from app.main import app
from tests.fakes import TOKEN_VALIDO, supabase_em_baixo, supabase_falso


def usar_supabase(handler):
    async def cliente_falso():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    app.dependency_overrides[get_http_client] = cliente_falso


@pytest.fixture
def api():
    usar_supabase(supabase_falso)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_estado(api):
    res = api.get("/api/estado")
    assert res.status_code == 200
    assert res.json() == {"ambiente": "development", "versao": "0.1.0", "supabase": "ligado"}


def test_estado_sem_supabase(api):
    usar_supabase(supabase_em_baixo)
    assert api.get("/api/estado").json()["supabase"] == "sem ligação"


def test_eu_exige_sessao(api):
    res = api.get("/api/eu")
    assert res.status_code == 401
    assert res.json()["detail"] == "É necessário iniciar sessão."


def test_eu_recusa_token_invalido(api):
    res = api.get("/api/eu", headers={"Authorization": "Bearer token-falso"})
    assert res.status_code == 401


def test_eu_com_sessao_valida(api):
    res = api.get("/api/eu", headers={"Authorization": f"Bearer {TOKEN_VALIDO}"})
    assert res.status_code == 200
    assert res.json() == {"id": "uuid-psicologa-ficticia", "email": "ana@exemplo.pt"}
