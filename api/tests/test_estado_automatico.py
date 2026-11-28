"""Passo 9: consultas terminadas passam sozinhas a "realizada", para o psicólogo confirmar."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fakes import SupabaseFalso
from tests.test_consultas import ANA, OUTRA, iso, marcar, paciente, usar_supabase

CONCLUIR = "/api/consultas/concluir-passadas"


@pytest.fixture
def api():
    usar_supabase(SupabaseFalso())
    yield TestClient(app)
    app.dependency_overrides.clear()


def agora():
    return datetime.now(UTC).replace(microsecond=0)


def consulta(api, cid, headers=ANA):
    res = api.get(f"/api/consultas/{cid}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def cenario(api):
    p = paciente(api)
    ext = {"ignorar_sobreposicao": True}
    return {
        "terminada": marcar(api, p, inicio=agora() - timedelta(hours=3), **ext)["id"],
        "a_decorrer": marcar(api, p, inicio=agora() - timedelta(minutes=20), **ext)["id"],
        "futura": marcar(api, p, inicio=agora() + timedelta(days=1), **ext)["id"],
        "cancelada": marcar(api, p, inicio=agora() - timedelta(days=2), estado="cancelada")["id"],
        "faltou": marcar(api, p, inicio=agora() - timedelta(days=3), estado="faltou", **ext)["id"],
    }


def test_exige_sessao(api):
    assert api.post(CONCLUIR).status_code == 401


def test_so_as_agendadas_que_ja_terminaram_passam_a_realizada(api):
    c = cenario(api)
    res = api.post(CONCLUIR, headers=ANA)
    assert res.status_code == 200, res.text
    assert [x["id"] for x in res.json()] == [c["terminada"]]

    terminada = consulta(api, c["terminada"])
    assert terminada["estado"] == "realizada"
    assert terminada["estado_automatico"] is True
    for nome, estado in [
        ("a_decorrer", "agendada"),
        ("futura", "agendada"),
        ("cancelada", "cancelada"),
        ("faltou", "faltou"),
    ]:
        x = consulta(api, c[nome])
        assert (x["estado"], x["estado_automatico"]) == (estado, False), nome


def test_chamar_outra_vez_nao_muda_nada(api):
    cenario(api)
    api.post(CONCLUIR, headers=ANA)
    assert api.post(CONCLUIR, headers=ANA).json() == []


def test_nao_mexe_nas_consultas_de_outra_psicologa(api):
    c = cenario(api)
    assert api.post(CONCLUIR, headers=OUTRA).json() == []
    assert consulta(api, c["terminada"])["estado"] == "agendada"


def test_a_agenda_mostra_o_estado_automatico(api):
    c = cenario(api)
    api.post(CONCLUIR, headers=ANA)
    params = {"de": iso(agora() - timedelta(days=7)), "ate": iso(agora() + timedelta(days=7))}
    lista = api.get("/api/consultas", params=params, headers=ANA).json()
    automaticas = [x["id"] for x in lista if x["estado_automatico"]]
    assert automaticas == [c["terminada"]]


def test_confirmar_realizada_tira_o_aviso(api):
    c = cenario(api)
    api.post(CONCLUIR, headers=ANA)
    res = api.patch(f"/api/consultas/{c['terminada']}", json={"estado": "realizada"}, headers=ANA)
    assert res.status_code == 200, res.text
    assert (res.json()["estado"], res.json()["estado_automatico"]) == ("realizada", False)


def test_mudar_para_faltou_ou_cancelada_tira_o_aviso(api):
    c = cenario(api)
    api.post(CONCLUIR, headers=ANA)
    for estado in ("faltou", "cancelada"):
        res = api.patch(f"/api/consultas/{c['terminada']}", json={"estado": estado}, headers=ANA)
        assert res.status_code == 200, res.text
        assert (res.json()["estado"], res.json()["estado_automatico"]) == (estado, False)


def test_guardar_so_as_notas_nao_conta_como_confirmacao(api):
    c = cenario(api)
    api.post(CONCLUIR, headers=ANA)
    res = api.patch(
        f"/api/consultas/{c['terminada']}", json={"notas": "Notas fictícias."}, headers=ANA
    )
    assert res.status_code == 200, res.text
    assert res.json()["estado_automatico"] is True


def test_o_estado_automatico_nao_se_envia_pela_api(api):
    c = cenario(api)
    corpo = {"estado_automatico": False}
    assert api.patch(f"/api/consultas/{c['terminada']}", json=corpo, headers=ANA).status_code == 422
    p = paciente(api, nome="Outro")
    marcar(api, p, inicio=agora() + timedelta(days=2), esperado=422, estado_automatico=True)
