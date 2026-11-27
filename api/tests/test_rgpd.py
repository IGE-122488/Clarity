"""Passo 7 (RGPD): exportar todos os dados de um paciente e apagá-lo definitivamente."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fakes import SupabaseFalso
from tests.test_briefings import PROXIMA, sessao
from tests.test_consultas import ANA, ID_INEXISTENTE, OUTRA, marcar, paciente, usar_supabase

NOME = "Maria Fictícia"
INICIO = datetime(2020, 1, 1, tzinfo=UTC)


@pytest.fixture
def sb():
    falso = SupabaseFalso()
    usar_supabase(falso)
    yield falso
    app.dependency_overrides.clear()


@pytest.fixture
def api(sb):
    return TestClient(app)


@pytest.fixture
def cenario(api, sb):
    """Maria com 2 sessões realizadas (uma com briefing) e outro paciente da mesma psicóloga."""
    p = paciente(api, nome=NOME)
    antiga = sessao(api, p, 14, notas="Notas fictícias da sessão antiga.")
    recente = sessao(api, p, 7, notas="Notas fictícias da sessão recente.")
    sb.tabelas["briefings"].append(
        {
            "id": "00000000-0000-4000-8000-0000000000b1",
            "psicologo_id": "uuid-psicologa-ficticia",
            "consulta_id": recente,
            "texto": "Briefing fictício",
            "revisto": True,
            "modelo": "gpt-5-mini-teste",
            "sessoes_usadas": 1,
            "gerado_em": "2030-01-21T11:00:00Z",
            "criado_em": "2030-01-21T11:00:00Z",
            "atualizado_em": "2030-01-21T11:00:00Z",
        }
    )
    outro = paciente(api, nome="Outro paciente")
    marcar(api, outro, inicio=PROXIMA + timedelta(days=1))
    return {"paciente": p, "antiga": antiga, "recente": recente, "outro": outro}


def exportar(api, paciente_id, headers=ANA):
    return api.get(f"/api/pacientes/{paciente_id}/exportar", headers=headers)


def apagar(api, paciente_id, confirmacao=NOME, headers=ANA):
    return api.request(
        "DELETE",
        f"/api/pacientes/{paciente_id}",
        json={"confirmacao": confirmacao},
        headers=headers,
    )


# Exportar


def test_exporta_ficha_consultas_notas_e_briefings(api, cenario):
    res = exportar(api, cenario["paciente"])
    assert res.status_code == 200, res.text
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["content-disposition"].startswith("attachment;")
    dados = res.json()
    assert dados["formato"] == "clarity.exportacao-paciente"
    assert dados["paciente"]["nome"] == NOME
    consultas = dados["consultas"]
    assert [c["id"] for c in consultas] == [cenario["antiga"], cenario["recente"]]  # antigas 1.º
    assert consultas[0]["notas"] == "Notas fictícias da sessão antiga."
    assert consultas[0]["briefing"] is None
    assert consultas[1]["briefing"]["texto"] == "Briefing fictício"
    assert consultas[1]["briefing"]["revisto"] is True


def test_exportar_nao_inclui_dados_de_outros_pacientes(api, cenario):
    consultas = exportar(api, cenario["paciente"]).json()["consultas"]
    assert len(consultas) == 2


def test_exportar_paciente_de_outra_psicologa_ou_inexistente_da_404(api, cenario):
    assert exportar(api, cenario["paciente"], headers=OUTRA).status_code == 404
    assert exportar(api, ID_INEXISTENTE).status_code == 404
    assert api.get(f"/api/pacientes/{cenario['paciente']}/exportar").status_code == 401


def test_exporta_todas_as_consultas_mesmo_acima_do_limite_do_supabase(api, sb):
    """O Supabase devolve no máximo 1000 linhas por pedido: a exportação lê página a página."""
    p = paciente(api, nome=NOME)
    for i in range(1205):
        sb.tabelas["consultas"].append(
            {
                "id": f"00000000-0000-4000-8000-{i:012d}",
                "psicologo_id": "uuid-psicologa-ficticia",
                "paciente_id": p,
                "inicio": f"{INICIO + timedelta(hours=i):%Y-%m-%dT%H:%M:%SZ}",
                "fim": "2030-01-01T00:00:00Z",
                "estado": "realizada",
                "notas": f"Nota {i}",
                "criado_em": "2020-01-01T00:00:00Z",
                "atualizado_em": "2020-01-01T00:00:00Z",
            }
        )
    consultas = exportar(api, p).json()["consultas"]
    assert len(consultas) == 1205
    assert len({c["id"] for c in consultas}) == 1205


# Apagar


def test_apagar_remove_paciente_consultas_notas_e_briefings(api, sb, cenario):
    res = apagar(api, cenario["paciente"])
    assert res.status_code == 204, res.text
    assert api.get(f"/api/pacientes/{cenario['paciente']}", headers=ANA).status_code == 404
    restantes = [c["paciente_id"] for c in sb.tabelas["consultas"]]
    assert restantes == [cenario["outro"]]
    assert sb.tabelas["briefings"] == []


def test_apagar_nao_mexe_noutros_pacientes(api, cenario):
    apagar(api, cenario["paciente"])
    pacientes = api.get("/api/pacientes", headers=ANA).json()
    assert [p["nome"] for p in pacientes] == ["Outro paciente"]
    assert len(api.get(f"/api/pacientes/{cenario['outro']}/consultas", headers=ANA).json()) == 1


@pytest.mark.parametrize("escrito", ["  maria   fictícia ", "MARIA FICTÍCIA"])
def test_confirmacao_ignora_maiusculas_e_espacos(api, cenario, escrito):
    assert apagar(api, cenario["paciente"], confirmacao=escrito).status_code == 204


@pytest.mark.parametrize("escrito", ["Maria Ficticia", "Maria", "Outro paciente"])
def test_nome_errado_nao_apaga_nada(api, sb, cenario, escrito):
    res = apagar(api, cenario["paciente"], confirmacao=escrito)
    assert res.status_code == 422
    assert "Nada foi apagado" in res.json()["detail"]
    assert len(sb.tabelas["pacientes"]) == 2
    assert len(sb.tabelas["consultas"]) == 3
    assert len(sb.tabelas["briefings"]) == 1


def test_sem_confirmacao_nao_apaga(api, sb, cenario):
    res = api.request("DELETE", f"/api/pacientes/{cenario['paciente']}", headers=ANA)
    assert res.status_code == 422
    assert len(sb.tabelas["pacientes"]) == 2


def test_outra_psicologa_nao_apaga(api, sb, cenario):
    assert apagar(api, cenario["paciente"], headers=OUTRA).status_code == 404
    assert len(sb.tabelas["pacientes"]) == 2
    assert apagar(api, ID_INEXISTENTE).status_code == 404


def test_consultas_e_briefings_nao_se_apagam_diretamente(sb, cenario):
    """Só o paciente tem DELETE: a Data API recusa apagar consultas ou briefings sozinhos."""
    pedido = httpx.Request(
        "DELETE",
        "https://falso.supabase.co/rest/v1/consultas",
        headers={"Authorization": f"Bearer {ANA['Authorization'].removeprefix('Bearer ')}"},
    )
    assert sb(pedido).status_code == 403
    pedido = httpx.Request(
        "DELETE", "https://falso.supabase.co/rest/v1/briefings", headers=pedido.headers
    )
    assert sb(pedido).status_code == 403
