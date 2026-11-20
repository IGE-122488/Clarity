import asyncio
import uuid

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
