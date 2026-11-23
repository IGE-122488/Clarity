import asyncio
import json

import httpx
import pytest

from app.config import read_settings
from app.ia import ErroIA, IANaoConfigurada, gerar_texto

CHAVE = "chave-ficticia-de-teste"
BASE = {
    "SUPABASE_URL": "https://exemplo.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
}
IA = {
    **BASE,
    "AZURE_OPENAI_BASE_URL": "https://recurso.services.ai.azure.com/openai/v1",
    "AZURE_OPENAI_API_KEY": CHAVE,
    "AZURE_OPENAI_DEPLOYMENT": "briefing",
}
NOTAS = "Notas fictícias e confidenciais"

RESPOSTA_OK = {
    "status": "completed",
    "model": "gpt-5-mini-2025-08-07",
    "output": [
        {"type": "reasoning", "summary": []},
        {
            "type": "message",
            "content": [
                {"type": "output_text", "text": "Resumo das últimas sessões\n"},
                {"type": "output_text", "text": "- Tudo fictício"},
            ],
        },
    ],
}


def gerar(handler, env=IA):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await gerar_texto(client, read_settings(env), instrucoes="Regras", entrada=NOTAS)

    return asyncio.run(go())


def test_pedido_ao_azure():
    pedidos = []

    def handler(request):
        pedidos.append(request)
        return httpx.Response(200, json=RESPOSTA_OK)

    resposta = gerar(handler)
    assert resposta.texto == "Resumo das últimas sessões\n- Tudo fictício"
    assert resposta.modelo == "gpt-5-mini-2025-08-07"

    pedido = pedidos[0]
    assert str(pedido.url) == "https://recurso.services.ai.azure.com/openai/v1/responses"
    assert pedido.headers["api-key"] == CHAVE
    corpo = json.loads(pedido.content)
    assert corpo["model"] == "briefing"
    assert corpo["instructions"] == "Regras"
    assert corpo["input"] == NOTAS
    assert corpo["store"] is False  # o Azure não guarda o pedido nem a resposta
    assert corpo["reasoning"] == {"effort": "low"}


def test_sem_configuracao_nao_faz_pedidos():
    def handler(request):
        raise AssertionError("não devia ter feito nenhum pedido")

    with pytest.raises(IANaoConfigurada):
        gerar(handler, env=BASE)


@pytest.mark.parametrize(
    ("resposta", "codigo"),
    [
        (httpx.Response(401, json={"error": {"code": "401"}}), 502),
        (httpx.Response(404, json={"error": {"code": "DeploymentNotFound"}}), 502),
        (httpx.Response(429, json={"error": {"code": "429"}}), 429),
        (httpx.Response(400, json={"error": {"code": "content_filter", "message": NOTAS}}), 422),
        (httpx.Response(400, json={"error": {"code": "bad_request", "message": NOTAS}}), 502),
        (httpx.Response(500, text=NOTAS), 502),
        (httpx.Response(200, json={**RESPOSTA_OK, "status": "incomplete"}), 502),
        (httpx.Response(200, json={"status": "completed", "output": []}), 502),
    ],
)
def test_erros_viram_mensagens_sem_dados(resposta, codigo):
    with pytest.raises(ErroIA) as erro:
        gerar(lambda _request: resposta)
    assert erro.value.codigo == codigo
    assert NOTAS not in str(erro.value)
    assert CHAVE not in str(erro.value)


def test_sem_rede_e_tempo_esgotado():
    def sem_rede(request):
        raise httpx.ConnectError("sem rede", request=request)

    def lento(request):
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(ErroIA) as erro:
        gerar(sem_rede)
    assert erro.value.codigo == 502
    with pytest.raises(ErroIA) as erro:
        gerar(lento)
    assert erro.value.codigo == 504
