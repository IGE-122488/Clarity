from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.ia import ErroIA, RespostaIA
from app.main import app
from app.routes.briefings import get_gerador
from tests.fakes import SupabaseFalso
from tests.test_consultas import ANA, ID_INEXISTENTE, OUTRA, marcar, paciente, usar_supabase

# Às 12h UTC para a data ser a mesma em Lisboa e em UTC (o Windows pode não ter fusos).
PROXIMA = datetime(2030, 1, 28, 12, 0, tzinfo=UTC)
NOME = "Maria Fictícia"


class GeradorFalso:
    """Faz de IA: devolve um texto fixo e guarda o que lhe foi enviado."""

    def __init__(self, texto="Resumo das últimas sessões\n- Tudo fictício (21/01/2030)"):
        self.texto = texto
        self.pedidos: list[dict] = []
        self.erro: ErroIA | None = None

    async def __call__(self, _client, _settings, *, instrucoes, entrada):
        self.pedidos.append({"instrucoes": instrucoes, "entrada": entrada})
        if self.erro is not None:
            raise self.erro
        return RespostaIA(texto=self.texto, modelo="gpt-5-mini-teste")


@pytest.fixture
def gerador():
    return GeradorFalso()


@pytest.fixture
def api(gerador):
    usar_supabase(SupabaseFalso())
    app.dependency_overrides[get_gerador] = lambda: gerador
    yield TestClient(app)
    app.dependency_overrides.clear()


def sessao(api, paciente_id, dias_antes, estado="realizada", notas=None, headers=ANA):
    inicio = PROXIMA - timedelta(days=dias_antes)
    c = marcar(api, paciente_id, inicio=inicio, headers=headers, ignorar_sobreposicao=True)
    corpo = {"estado": estado}
    if notas is not None:
        corpo["notas"] = notas
    res = api.patch(f"/api/consultas/{c['id']}", json=corpo, headers=headers)
    assert res.status_code == 200, res.text
    return c["id"]


@pytest.fixture
def cenario(api):
    """Paciente com 2 sessões realizadas com notas e a próxima consulta marcada."""
    p = paciente(api, nome=NOME)
    sessao(api, p, 14, notas="Notas fictícias da sessão A: ansiedade no trabalho.")
    sessao(api, p, 7, notas="Notas fictícias da sessão B: dormiu melhor.")
    proxima = marcar(api, p, inicio=PROXIMA)["id"]
    return {"paciente": p, "consulta": proxima}


def caminho(consulta_id):
    return f"/api/consultas/{consulta_id}/briefing"


# Sessão e acesso


@pytest.mark.parametrize("metodo", ["get", "post", "patch"])
def test_exige_sessao(api, metodo):
    assert api.request(metodo, caminho(ID_INEXISTENTE), json={}).status_code == 401


@pytest.mark.parametrize("metodo", ["get", "post"])
def test_consulta_inexistente_ou_de_outra_psicologa_da_404(api, cenario, metodo):
    assert api.request(metodo, caminho(ID_INEXISTENTE), headers=ANA).status_code == 404
    assert api.request(metodo, caminho(cenario["consulta"]), headers=OUTRA).status_code == 404


# Gerar


def test_sem_briefing_devolve_null(api, cenario):
    res = api.get(caminho(cenario["consulta"]), headers=ANA)
    assert res.status_code == 200
    assert res.json() is None


def test_gera_e_guarda_por_rever(api, cenario, gerador):
    res = api.post(caminho(cenario["consulta"]), headers=ANA)
    assert res.status_code == 200, res.text
    b = res.json()
    assert b["texto"] == gerador.texto
    assert b["revisto"] is False
    assert b["modelo"] == "gpt-5-mini-teste"
    assert b["sessoes_usadas"] == 2
    assert b["consulta_id"] == cenario["consulta"]

    assert api.get(caminho(cenario["consulta"]), headers=ANA).json()["id"] == b["id"]


def test_a_ia_so_recebe_datas_e_notas(api, cenario, gerador):
    api.post(caminho(cenario["consulta"]), headers=ANA)
    entrada = gerador.pedidos[0]["entrada"]
    assert "sessão A" in entrada and "sessão B" in entrada
    assert "Sessão de 14/01/2030" in entrada and "Sessão de 21/01/2030" in entrada
    assert "Data da próxima sessão: 28/01/2030" in entrada
    assert entrada.index("sessão A") < entrada.index("sessão B")  # ordem cronológica
    assert NOME not in entrada
    assert cenario["paciente"] not in entrada


def test_ignora_sessoes_que_nao_contam(api, cenario, gerador):
    p = cenario["paciente"]
    sessao(api, p, 3, estado="faltou", notas="Notas de falta")
    sessao(api, p, 2, estado="cancelada", notas="Notas de cancelada")
    sessao(api, p, 1, notas="   ")  # realizada mas sem notas
    sessao(api, p, -7, notas="Notas de uma sessão futura")
    outro = paciente(api, nome="Outro paciente")
    sessao(api, outro, 4, notas="Notas de outro paciente")

    res = api.post(caminho(cenario["consulta"]), headers=ANA)
    assert res.json()["sessoes_usadas"] == 2
    entrada = gerador.pedidos[0]["entrada"]
    for texto in ("falta", "cancelada", "futura", "outro paciente"):
        assert texto not in entrada


def test_sem_notas_anteriores_da_422_sem_chamar_a_ia(api, gerador):
    p = paciente(api)
    consulta = marcar(api, p, inicio=PROXIMA)["id"]
    res = api.post(caminho(consulta), headers=ANA)
    assert res.status_code == 422
    assert "notas" in res.json()["detail"]
    assert gerador.pedidos == []


def test_consulta_cancelada_da_409(api, cenario, gerador):
    api.patch(f"/api/consultas/{cenario['consulta']}", json={"estado": "cancelada"}, headers=ANA)
    assert api.post(caminho(cenario["consulta"]), headers=ANA).status_code == 409
    assert gerador.pedidos == []


def test_gerar_de_novo_substitui_e_volta_a_por_rever(api, cenario, gerador):
    primeiro = api.post(caminho(cenario["consulta"]), headers=ANA).json()
    api.patch(caminho(cenario["consulta"]), json={"revisto": True}, headers=ANA)

    gerador.texto = "Texto novo"
    segundo = api.post(caminho(cenario["consulta"]), headers=ANA).json()
    assert segundo["id"] == primeiro["id"]  # continua a haver só um por consulta
    assert segundo["texto"] == "Texto novo"
    assert segundo["revisto"] is False


@pytest.mark.parametrize("codigo", [429, 502, 504, 422])
def test_erros_da_ia_chegam_a_app_com_mensagem_clara(api, cenario, gerador, codigo):
    gerador.erro = ErroIA("Mensagem para o psicólogo.", codigo)
    res = api.post(caminho(cenario["consulta"]), headers=ANA)
    assert res.status_code == codigo
    assert res.json()["detail"] == "Mensagem para o psicólogo."
    assert api.get(caminho(cenario["consulta"]), headers=ANA).json() is None  # nada guardado


def test_sem_ia_configurada_da_503(cenario):
    # Sem substituir o gerador: os testes não têm variáveis AZURE_OPENAI_*.
    app.dependency_overrides.pop(get_gerador)
    res = TestClient(app).post(caminho(cenario["consulta"]), headers=ANA)
    assert res.status_code == 503


# Rever e editar


def test_editar_e_marcar_revisto(api, cenario):
    api.post(caminho(cenario["consulta"]), headers=ANA)
    res = api.patch(
        caminho(cenario["consulta"]),
        json={"texto": "  Texto revisto  ", "revisto": True},
        headers=ANA,
    )
    assert res.status_code == 200, res.text
    assert res.json()["texto"] == "Texto revisto"
    assert res.json()["revisto"] is True


@pytest.mark.parametrize(
    "corpo", [{}, {"texto": ""}, {"texto": None}, {"revisto": None}, {"modelo": "outro"}]
)
def test_alteracoes_invalidas_dao_422(api, cenario, corpo):
    api.post(caminho(cenario["consulta"]), headers=ANA)
    assert api.patch(caminho(cenario["consulta"]), json=corpo, headers=ANA).status_code == 422


def test_editar_sem_briefing_ou_de_outra_psicologa_da_404(api, cenario):
    assert (
        api.patch(caminho(cenario["consulta"]), json={"revisto": True}, headers=ANA).status_code
        == 404
    )
    api.post(caminho(cenario["consulta"]), headers=ANA)
    res = api.patch(caminho(cenario["consulta"]), json={"texto": "Do B"}, headers=OUTRA)
    assert res.status_code == 404
