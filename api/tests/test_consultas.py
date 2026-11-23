from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.deps import get_http_client
from app.main import app
from tests.fakes import TOKEN_OUTRA, TOKEN_VALIDO, SupabaseFalso, supabase_em_baixo

ANA = {"Authorization": f"Bearer {TOKEN_VALIDO}"}
OUTRA = {"Authorization": f"Bearer {TOKEN_OUTRA}"}

SEG_10H = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)
SEGUNDA = SEG_10H.replace(hour=0)
ID_INEXISTENTE = "00000000-0000-4000-8000-000000000001"


def iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def paciente(api, headers=ANA, nome="Paciente fictício"):
    res = api.post("/api/pacientes", json={"nome": nome}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def marcar(api, paciente_id, inicio=SEG_10H, minutos=50, headers=ANA, esperado=201, **extra):
    corpo = {
        "paciente_id": paciente_id,
        "inicio": iso(inicio),
        "fim": iso(inicio + timedelta(minutes=minutos)),
        **extra,
    }
    res = api.post("/api/consultas", json=corpo, headers=headers)
    assert res.status_code == esperado, res.text
    return res.json()


def semana(api, segunda=SEGUNDA, headers=ANA):
    params = {"de": iso(segunda), "ate": iso(segunda + timedelta(days=7))}
    return api.get("/api/consultas", params=params, headers=headers)


# Sessão


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("get", "/api/consultas?de=2030-01-07T00:00:00Z&ate=2030-01-14T00:00:00Z"),
        ("post", "/api/consultas"),
        ("get", f"/api/consultas/{ID_INEXISTENTE}"),
        ("patch", f"/api/consultas/{ID_INEXISTENTE}"),
        ("get", f"/api/pacientes/{ID_INEXISTENTE}/consultas"),
    ],
)
def test_exige_sessao(api, metodo, caminho):
    assert api.request(metodo, caminho, json={}).status_code == 401


# Marcar e ver a agenda


def test_marcar_e_ver_na_agenda_sem_notas(api):
    p = paciente(api)
    consulta = marcar(api, p, notas="Notas fictícias")
    assert consulta["estado"] == "agendada"
    assert consulta["notas"] == "Notas fictícias"

    res = semana(api)
    assert res.status_code == 200
    assert [c["id"] for c in res.json()] == [consulta["id"]]
    assert "notas" not in res.json()[0]  # a agenda não traz as notas


def test_agenda_so_mostra_o_intervalo_pedido(api):
    p = paciente(api)
    marcar(api, p)
    marcar(api, p, inicio=SEG_10H + timedelta(days=8))
    assert len(semana(api).json()) == 1


def test_hora_com_fuso_e_guardada_em_utc(api):
    p = paciente(api)
    res = api.post(
        "/api/consultas",
        json={
            "paciente_id": p,
            "inicio": "2030-07-01T10:00:00+01:00",
            "fim": "2030-07-01T10:50:00+01:00",
        },
        headers=ANA,
    )
    assert res.status_code == 201, res.text
    assert datetime.fromisoformat(res.json()["inicio"]) == datetime(2030, 7, 1, 9, 0, tzinfo=UTC)


def test_ver_consulta_com_notas(api):
    p = paciente(api)
    consulta = marcar(api, p, notas="Notas fictícias")
    res = api.get(f"/api/consultas/{consulta['id']}", headers=ANA)
    assert res.status_code == 200
    assert res.json()["notas"] == "Notas fictícias"


def test_historico_do_paciente(api):
    p = paciente(api)
    marcar(api, p, notas="Primeira")
    marcar(api, p, inicio=SEG_10H + timedelta(days=7), notas="Segunda")
    res = api.get(f"/api/pacientes/{p}/consultas", headers=ANA)
    assert res.status_code == 200
    assert [c["notas"] for c in res.json()] == ["Segunda", "Primeira"]


def test_historico_de_paciente_inexistente(api):
    assert api.get(f"/api/pacientes/{ID_INEXISTENTE}/consultas", headers=ANA).status_code == 404


# Sobreposição de horários


def test_sobreposicao_avisa_com_409_e_lista_o_conflito(api):
    p = paciente(api)
    primeira = marcar(api, p)
    res = api.post(
        "/api/consultas",
        json={
            "paciente_id": p,
            "inicio": iso(SEG_10H + timedelta(minutes=30)),
            "fim": iso(SEG_10H + timedelta(minutes=80)),
        },
        headers=ANA,
    )
    assert res.status_code == 409
    detalhe = res.json()["detail"]
    assert "Já tem outra consulta" in detalhe["mensagem"]
    assert [c["id"] for c in detalhe["sobrepostas"]] == [primeira["id"]]
    assert len(semana(api).json()) == 1  # nada foi gravado


def test_sobreposicao_confirmada_marca_na_mesma(api):
    p = paciente(api)
    marcar(api, p)
    marcar(api, p, inicio=SEG_10H + timedelta(minutes=30), ignorar_sobreposicao=True)
    assert len(semana(api).json()) == 2


def test_consultas_encostadas_nao_se_sobrepoem(api):
    p = paciente(api)
    marcar(api, p)
    marcar(api, p, inicio=SEG_10H + timedelta(minutes=50))


def test_consulta_cancelada_liberta_o_horario(api):
    p = paciente(api)
    consulta = marcar(api, p)
    api.patch(f"/api/consultas/{consulta['id']}", json={"estado": "cancelada"}, headers=ANA)
    marcar(api, p)


def test_remarcar_para_horario_ocupado_avisa(api):
    p = paciente(api)
    marcar(api, p)
    outra = marcar(api, p, inicio=SEG_10H + timedelta(hours=2))
    res = api.patch(
        f"/api/consultas/{outra['id']}",
        json={"inicio": iso(SEG_10H + timedelta(minutes=20))},
        headers=ANA,
    )
    assert res.status_code == 409


def test_alterar_notas_nao_verifica_sobreposicao(api):
    p = paciente(api)
    marcar(api, p)
    sobreposta = marcar(api, p, ignorar_sobreposicao=True)
    res = api.patch(f"/api/consultas/{sobreposta['id']}", json={"notas": "Ok"}, headers=ANA)
    assert res.status_code == 200


def test_reativar_cancelada_para_horario_ocupado_avisa(api):
    p = paciente(api)
    cancelada = marcar(api, p, estado="cancelada")
    marcar(api, p)
    res = api.patch(f"/api/consultas/{cancelada['id']}", json={"estado": "agendada"}, headers=ANA)
    assert res.status_code == 409


# Remarcar, cancelar, notas


def test_remarcar_mantem_a_duracao_se_mudar_os_dois(api):
    p = paciente(api)
    consulta = marcar(api, p)
    novo = SEG_10H + timedelta(days=1)
    res = api.patch(
        f"/api/consultas/{consulta['id']}",
        json={"inicio": iso(novo), "fim": iso(novo + timedelta(minutes=50))},
        headers=ANA,
    )
    assert res.status_code == 200, res.text
    assert datetime.fromisoformat(res.json()["inicio"]) == novo


def test_remarcar_so_o_inicio_para_depois_do_fim_e_recusado(api):
    p = paciente(api)
    consulta = marcar(api, p)
    res = api.patch(
        f"/api/consultas/{consulta['id']}",
        json={"inicio": iso(SEG_10H + timedelta(hours=2))},
        headers=ANA,
    )
    assert res.status_code == 422
    assert "acabar depois de começar" in res.json()["detail"]


def test_escrever_e_limpar_notas(api):
    p = paciente(api)
    consulta = marcar(api, p)
    caminho = f"/api/consultas/{consulta['id']}"
    assert api.patch(caminho, json={"notas": "Notas fictícias"}, headers=ANA).json()["notas"] == (
        "Notas fictícias"
    )
    assert api.patch(caminho, json={"notas": None}, headers=ANA).json()["notas"] is None


def test_marcar_como_realizada_e_faltou(api):
    p = paciente(api)
    consulta = marcar(api, p)
    caminho = f"/api/consultas/{consulta['id']}"
    assert api.patch(caminho, json={"estado": "realizada"}, headers=ANA).json()["estado"] == (
        "realizada"
    )
    assert api.patch(caminho, json={"estado": "faltou"}, headers=ANA).json()["estado"] == "faltou"


# Isolamento entre psicólogos


def test_outra_psicologa_nao_ve_nem_altera(api):
    p = paciente(api)
    consulta = marcar(api, p, notas="Notas da Ana")
    caminho = f"/api/consultas/{consulta['id']}"

    assert semana(api, headers=OUTRA).json() == []
    assert api.get(caminho, headers=OUTRA).status_code == 404
    assert api.patch(caminho, json={"notas": "Pirata"}, headers=OUTRA).status_code == 404
    assert api.get(f"/api/pacientes/{p}/consultas", headers=OUTRA).status_code == 404
    assert api.get(caminho, headers=ANA).json()["notas"] == "Notas da Ana"


def test_outra_psicologa_nao_marca_para_paciente_da_ana(api):
    p = paciente(api)
    marcar(api, p, headers=OUTRA, esperado=404)


def test_sobreposicao_nao_mistura_psicologos(api):
    marcar(api, paciente(api))
    marcar(api, paciente(api, headers=OUTRA), headers=OUTRA)  # mesmo horário, outra psicóloga


# Validação


def test_paciente_arquivado_nao_recebe_consultas(api):
    p = paciente(api)
    api.patch(f"/api/pacientes/{p}", json={"ativo": False}, headers=ANA)
    res = marcar(api, p, esperado=409)
    assert "arquivado" in res["detail"]


def test_paciente_inexistente(api):
    marcar(api, ID_INEXISTENTE, esperado=404)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"fim": iso(SEG_10H)},  # acaba quando começa
        {"fim": iso(SEG_10H - timedelta(minutes=10))},  # acaba antes de começar
        {"fim": iso(SEG_10H + timedelta(hours=9))},  # mais de 8 horas
        {"inicio": "2030-01-07T10:00:00"},  # sem fuso horário
        {"estado": "inventado"},
        {"psicologo_id": "uuid-outra-psicologa"},
        {"notas": "x" * 20001},
    ],
)
def test_marcar_recusa_dados_invalidos(api, alteracao):
    p = paciente(api)
    corpo = {
        "paciente_id": p,
        "inicio": iso(SEG_10H),
        "fim": iso(SEG_10H + timedelta(minutes=50)),
        **alteracao,
    }
    assert api.post("/api/consultas", json=corpo, headers=ANA).status_code == 422


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"ignorar_sobreposicao": True},
        {"inicio": None},
        {"estado": None},
        {"paciente_id": ID_INEXISTENTE},
    ],
)
def test_alterar_recusa_dados_invalidos(api, corpo):
    consulta = marcar(api, paciente(api))
    assert api.patch(f"/api/consultas/{consulta['id']}", json=corpo, headers=ANA).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"de": "2030-01-07T00:00:00Z"},  # falta "ate"
        {"de": "2030-01-14T00:00:00Z", "ate": "2030-01-07T00:00:00Z"},  # ao contrário
        {"de": "2030-01-01T00:00:00Z", "ate": "2030-06-01T00:00:00Z"},  # mais de 62 dias
        {"de": "2030-01-07T00:00:00", "ate": "2030-01-14T00:00:00"},  # sem fuso horário
    ],
)
def test_agenda_recusa_intervalos_invalidos(api, params):
    assert api.get("/api/consultas", params=params, headers=ANA).status_code == 422


def test_base_de_dados_em_baixo(api):
    usar_supabase(supabase_em_baixo)
    assert semana(api).status_code == 502
