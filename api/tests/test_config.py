import pytest

from app.config import ConfigError, read_settings

OK = {
    "SUPABASE_URL": "https://exemplo.supabase.co/",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
}


def test_le_variaveis_e_usa_development_por_omissao():
    s = read_settings(OK)
    assert s.supabase_url == "https://exemplo.supabase.co"
    assert s.app_env == "development"
    assert s.commit is None


def test_falha_com_mensagem_clara_se_faltar_variavel():
    with pytest.raises(ConfigError, match="SUPABASE_PUBLISHABLE_KEY"):
        read_settings({"SUPABASE_URL": "https://x.supabase.co"})


def test_recusa_ambiente_desconhecido():
    with pytest.raises(ConfigError, match="APP_ENV"):
        read_settings({**OK, "APP_ENV": "teste"})


def test_le_commit_do_vercel():
    assert read_settings({**OK, "VERCEL_GIT_COMMIT_SHA": "abcdef1234"}).commit == "abcdef1"


def test_ia_e_opcional():
    s = read_settings(OK)
    assert s.ia_configurada is False


def test_le_ia_e_aceita_o_endereco_copiado_do_portal():
    s = read_settings(
        {
            **OK,
            "AZURE_OPENAI_BASE_URL": "https://r.services.ai.azure.com/openai/v1/responses",
            "AZURE_OPENAI_API_KEY": " chave-ficticia ",
            "AZURE_OPENAI_DEPLOYMENT": "briefing",
        }
    )
    assert s.ia_configurada
    assert s.ia_base_url == "https://r.services.ai.azure.com/openai/v1"
    assert s.ia_api_key == "chave-ficticia"
    assert "chave-ficticia" not in repr(s)  # a chave nunca aparece em registos


def test_endereco_da_ia_invalido_desliga_so_a_ia():
    s = read_settings(
        {
            **OK,
            "AZURE_OPENAI_BASE_URL": "http://inseguro.example",
            "AZURE_OPENAI_API_KEY": "x",
            "AZURE_OPENAI_DEPLOYMENT": "briefing",
        }
    )
    assert s.ia_configurada is False
