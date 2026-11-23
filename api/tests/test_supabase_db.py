import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import supabase_db as db
from app.config import read_settings
from tests.fakes import TOKEN_OUTRA, TOKEN_VALIDO, SupabaseFalso, supabase_em_baixo

SETTINGS = read_settings(
    {"SUPABASE_URL": "https://exemplo.supabase.co", "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x"}
)


def run(coro_factory, handler):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await coro_factory(client)

    return asyncio.run(go())


def responde(codigo):
    return lambda request: httpx.Response(codigo, json={"message": "dados internos"})


def test_pedido_leva_chave_publishable_e_token_do_psicologo():
    supabase = SupabaseFalso()
    run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_VALIDO), supabase)
    pedido = supabase.pedidos[0]
    assert pedido.headers["apikey"] == "sb_publishable_x"
    assert pedido.headers["Authorization"] == f"Bearer {TOKEN_VALIDO}"
    assert pedido.url.params["ativo"] == "is.true"
    assert pedido.url.params["order"] == "nome.asc"


def test_listar_com_arquivados_nao_filtra_ativo():
    supabase = SupabaseFalso()
    run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_VALIDO, incluir_arquivados=True), supabase)
    assert "ativo" not in supabase.pedidos[0].url.params


def test_criar_obter_e_atualizar():
    supabase = SupabaseFalso()
    novo = run(
        lambda c: db.criar_paciente(c, SETTINGS, TOKEN_VALIDO, {"nome": "Paciente fictício"}),
        supabase,
    )
    assert novo["nome"] == "Paciente fictício"
    assert "psicologo_id" not in novo
    assert supabase.pedidos[0].headers["Prefer"] == "return=representation"

    pid = uuid.UUID(novo["id"])
    assert (
        run(lambda c: db.obter_paciente(c, SETTINGS, TOKEN_VALIDO, pid), supabase)["id"]
        == (novo["id"])
    )
    alterado = run(
        lambda c: db.atualizar_paciente(c, SETTINGS, TOKEN_VALIDO, pid, {"ativo": False}),
        supabase,
    )
    assert alterado["ativo"] is False


def test_outra_psicologa_nao_ve_nem_altera():
    supabase = SupabaseFalso()
    novo = run(
        lambda c: db.criar_paciente(c, SETTINGS, TOKEN_VALIDO, {"nome": "Paciente fictício"}),
        supabase,
    )
    pid = uuid.UUID(novo["id"])
    assert run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_OUTRA), supabase) == []
    assert run(lambda c: db.obter_paciente(c, SETTINGS, TOKEN_OUTRA, pid), supabase) is None
    assert (
        run(
            lambda c: db.atualizar_paciente(c, SETTINGS, TOKEN_OUTRA, pid, {"nome": "X"}),
            supabase,
        )
        is None
    )


@pytest.mark.parametrize(
    ("codigo", "erro"),
    [
        (401, db.SessaoInvalida),
        (403, db.SemPermissao),
        (400, db.ErroBaseDados),
        (500, db.ErroBaseDados),
    ],
)
def test_erros_da_base_de_dados(codigo, erro):
    with pytest.raises(erro) as info:
        run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_VALIDO), responde(codigo))
    assert "dados internos" not in str(info.value)


def test_sem_rede():
    with pytest.raises(db.ErroBaseDados):
        run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_VALIDO), supabase_em_baixo)


# Consultas

SEG_10H = datetime(2030, 1, 7, 10, 0, tzinfo=UTC)


def _paciente(supabase, token=TOKEN_VALIDO):
    return run(
        lambda c: db.criar_paciente(c, SETTINGS, token, {"nome": "Paciente fictício"}), supabase
    )


def _consulta(supabase, paciente_id, inicio=SEG_10H, minutos=50, token=TOKEN_VALIDO, **extra):
    dados = {
        "paciente_id": paciente_id,
        "inicio": db.iso_utc(inicio),
        "fim": db.iso_utc(inicio + timedelta(minutes=minutos)),
        **extra,
    }
    return run(lambda c: db.criar_consulta(c, SETTINGS, token, dados), supabase)


def test_iso_utc_converte_para_utc():
    lisboa_verao = datetime.fromisoformat("2030-07-01T10:00:00+01:00")
    assert db.iso_utc(lisboa_verao) == "2030-07-01T09:00:00Z"


def test_agenda_filtra_pelo_intervalo_e_nao_traz_notas():
    supabase = SupabaseFalso()
    p = _paciente(supabase)
    _consulta(supabase, p["id"], notas="Notas fictícias")
    _consulta(supabase, p["id"], inicio=SEG_10H + timedelta(days=10))

    semana = run(
        lambda c: db.listar_consultas(
            c,
            SETTINGS,
            TOKEN_VALIDO,
            de=SEG_10H - timedelta(hours=10),
            ate=SEG_10H + timedelta(days=7),
        ),
        supabase,
    )
    assert len(semana) == 1
    assert "notas" not in semana[0]


def test_sobrepostas_ignora_canceladas_e_a_propria():
    supabase = SupabaseFalso()
    p = _paciente(supabase)
    a = _consulta(supabase, p["id"])
    _consulta(supabase, p["id"], estado="cancelada")

    def sobrepostas(inicio, fim, excluir=None):
        return run(
            lambda c: db.consultas_sobrepostas(
                c, SETTINGS, TOKEN_VALIDO, inicio=inicio, fim=fim, excluir_id=excluir
            ),
            supabase,
        )

    meio = SEG_10H + timedelta(minutes=30)
    assert [c["id"] for c in sobrepostas(meio, meio + timedelta(hours=1))] == [a["id"]]
    assert sobrepostas(meio, meio + timedelta(hours=1), uuid.UUID(a["id"])) == []
    # encostadas (uma acaba às 10:50 e a outra começa às 10:50) não se sobrepõem
    fim_a = SEG_10H + timedelta(minutes=50)
    assert sobrepostas(fim_a, fim_a + timedelta(minutes=50)) == []


def test_consulta_para_paciente_de_outra_psicologa_da_conflito():
    supabase = SupabaseFalso()
    da_ana = _paciente(supabase)
    with pytest.raises(db.Conflito):
        _consulta(supabase, da_ana["id"], token=TOKEN_OUTRA)


def test_historico_do_paciente_mais_recente_primeiro():
    supabase = SupabaseFalso()
    p = _paciente(supabase)
    _consulta(supabase, p["id"])
    _consulta(supabase, p["id"], inicio=SEG_10H + timedelta(days=7), notas="Segunda")
    historico = run(
        lambda c: db.listar_consultas_paciente(c, SETTINGS, TOKEN_VALIDO, uuid.UUID(p["id"])),
        supabase,
    )
    assert [c["notas"] for c in historico] == ["Segunda", None]


def test_409_da_conflito():
    with pytest.raises(db.Conflito):
        run(lambda c: db.listar_pacientes(c, SETTINGS, TOKEN_VALIDO), responde(409))
