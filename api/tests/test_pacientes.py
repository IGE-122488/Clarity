import httpx
import pytest
from fastapi.testclient import TestClient

from app.deps import get_http_client
from app.main import app
from tests.fakes import TOKEN_OUTRA, TOKEN_VALIDO, SupabaseFalso, supabase_em_baixo

ANA = {"Authorization": f"Bearer {TOKEN_VALIDO}"}
OUTRA = {"Authorization": f"Bearer {TOKEN_OUTRA}"}


def usar_supabase(handler):
    async def cliente_falso():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    app.dependency_overrides[get_http_client] = cliente_falso


@pytest.fixture
def api():
    usar_supabase(SupabaseFalso())
    yield TestClient(app)
    app.dependency_overrides.clear()


def criar(api, nome="Paciente fictício", headers=ANA, **extra):
    res = api.post("/api/pacientes", json={"nome": nome, **extra}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# Sessão


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "/api/pacientes"),
        ("post", "/api/pacientes"),
        ("get", "/api/pacientes/00000000-0000-4000-8000-000000000001"),
        ("patch", "/api/pacientes/00000000-0000-4000-8000-000000000001"),
    ],
)
def test_exige_sessao(api, metodo, caminho):
    res = api.request(metodo, caminho, json={"nome": "X"})
    assert res.status_code == 401


def test_token_vazio(api):
    assert api.get("/api/pacientes", headers={"Authorization": "Bearer "}).status_code == 401


def test_token_recusado_pelo_supabase(api):
    res = api.get("/api/pacientes", headers={"Authorization": "Bearer token-falso"})
    assert res.status_code == 401
    assert "Inicie sessão" in res.json()["detail"]


# Criar, listar, obter, alterar


def test_criar_e_listar_por_ordem_alfabetica(api):
    criar(api, "Rita Fictícia")
    criar(api, "  Bruno Fictício  ", data_nascimento="1990-05-17")

    res = api.get("/api/pacientes", headers=ANA)
    assert res.status_code == 200
    nomes = [p["nome"] for p in res.json()]
    assert nomes == ["Bruno Fictício", "Rita Fictícia"]  # espaços a mais retirados
    assert res.json()[0]["data_nascimento"] == "1990-05-17"
    assert "psicologo_id" not in res.json()[0]


def test_obter(api):
    paciente = criar(api)
    res = api.get(f"/api/pacientes/{paciente['id']}", headers=ANA)
    assert res.status_code == 200
    assert res.json()["nome"] == "Paciente fictício"


def test_obter_inexistente(api):
    res = api.get("/api/pacientes/00000000-0000-4000-8000-000000000001", headers=ANA)
    assert res.status_code == 404
    assert res.json()["detail"] == "Paciente não encontrado."


def test_id_invalido(api):
    assert api.get("/api/pacientes/nao-e-um-uuid", headers=ANA).status_code == 422


def test_alterar_so_o_que_foi_enviado(api):
    paciente = criar(api, data_nascimento="1985-01-02")
    res = api.patch(f"/api/pacientes/{paciente['id']}", json={"nome": "Novo nome"}, headers=ANA)
    assert res.status_code == 200
    assert res.json()["nome"] == "Novo nome"
    assert res.json()["data_nascimento"] == "1985-01-02"


def test_arquivar(api):
    paciente = criar(api)
    res = api.patch(f"/api/pacientes/{paciente['id']}", json={"ativo": False}, headers=ANA)
    assert res.status_code == 200

    assert api.get("/api/pacientes", headers=ANA).json() == []
    arquivados = api.get("/api/pacientes?arquivados=true", headers=ANA).json()
    assert [p["id"] for p in arquivados] == [paciente["id"]]


# Isolamento entre psicólogos (o mais importante)


def test_outra_psicologa_nao_ve_nem_altera(api):
    paciente = criar(api, "Paciente da Ana")
    caminho = f"/api/pacientes/{paciente['id']}"

    assert api.get("/api/pacientes", headers=OUTRA).json() == []
    assert api.get(caminho, headers=OUTRA).status_code == 404
    assert api.patch(caminho, json={"nome": "Pirata"}, headers=OUTRA).status_code == 404

    # O paciente da Ana ficou igual
    assert api.get(caminho, headers=ANA).json()["nome"] == "Paciente da Ana"


# Validação


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"nome": ""},
        {"nome": "   "},
        {"nome": "x" * 121},
        {"nome": "Ok", "data_nascimento": "2999-01-01"},
        {"nome": "Ok", "data_nascimento": "1850-01-01"},
        {"nome": "Ok", "psicologo_id": "uuid-outra-psicologa"},
        {"nome": "Ok", "ativo": False},
    ],
)
def test_criar_recusa_dados_invalidos(api, corpo):
    assert api.post("/api/pacientes", json=corpo, headers=ANA).status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [{}, {"nome": None}, {"ativo": None}, {"nome": ""}, {"psicologo_id": "uuid-outra-psicologa"}],
)
def test_alterar_recusa_dados_invalidos(api, corpo):
    paciente = criar(api)
    res = api.patch(f"/api/pacientes/{paciente['id']}", json=corpo, headers=ANA)
    assert res.status_code == 422


def test_alterar_pode_limpar_data_de_nascimento(api):
    paciente = criar(api, data_nascimento="1990-05-17")
    res = api.patch(f"/api/pacientes/{paciente['id']}", json={"data_nascimento": None}, headers=ANA)
    assert res.status_code == 200
    assert res.json()["data_nascimento"] is None


# Base de dados em baixo


def test_base_de_dados_em_baixo(api):
    usar_supabase(supabase_em_baixo)
    res = api.get("/api/pacientes", headers=ANA)
    assert res.status_code == 502
    assert res.json()["detail"].startswith("Não foi possível contactar a base de dados")
