import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import ocr as modulo_ocr
from app.config import read_settings
from app.main import app
from app.ocr import DOCX, TAMANHO_MAXIMO, ErroOCR, OCRNaoConfigurado, ler_texto
from app.routes.ocr import get_leitor
from tests.fakes import SupabaseFalso
from tests.test_consultas import ANA, usar_supabase

ENDPOINT = "https://clarity-ocr.cognitiveservices.azure.com"
CHAVE = "chave-ocr-ficticia"
ENV = {
    "SUPABASE_URL": "https://exemplo.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
    "AZURE_DOCINTEL_ENDPOINT": ENDPOINT + "/",
    "AZURE_DOCINTEL_KEY": CHAVE,
}
IMAGEM = b"\xff\xd8\xff fotografia ficticia"
TEXTO = "Sessão 3. Paciente refere que dormiu melhor."
RESULTADO = f"{ENDPOINT}/documentintelligence/documentModels/prebuilt-read/analyzeResults/abc"


class AzureFalso:
    """Imita o Document Intelligence: aceita a imagem, fica 'running' uma vez e depois responde."""

    def __init__(self, resposta_final=None, operacao=RESULTADO, primeiro=None):
        self.pedidos: list[httpx.Request] = []
        self.resposta_final = resposta_final or {
            "status": "succeeded",
            "analyzeResult": {"content": f"  {TEXTO}\n"},
        }
        self.operacao = operacao
        self.primeiro = primeiro
        self.consultas = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request)
        if request.method == "POST":
            if self.primeiro is not None:
                return self.primeiro
            return httpx.Response(202, headers={"operation-location": self.operacao})
        if request.method == "GET":
            self.consultas += 1
            if self.consultas == 1:
                return httpx.Response(200, json={"status": "running"})
            return httpx.Response(200, json=self.resposta_final)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(405)


def ler(handler, env=ENV):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await ler_texto(client, read_settings(env), IMAGEM, "image/jpeg", espera=0)

    return asyncio.run(go())


# Ligação ao Azure


def test_le_o_texto_e_apaga_o_resultado_no_azure():
    azure = AzureFalso()
    assert ler(azure) == TEXTO

    envio = azure.pedidos[0]
    assert envio.method == "POST"
    assert str(envio.url).startswith(
        f"{ENDPOINT}/documentintelligence/documentModels/prebuilt-read:analyze"
    )
    assert envio.url.params["api-version"] == "2024-11-30"
    assert envio.headers["Ocp-Apim-Subscription-Key"] == CHAVE
    assert envio.headers["Content-Type"] == "image/jpeg"
    assert envio.content == IMAGEM

    assert [p.method for p in azure.pedidos] == ["POST", "GET", "GET", "DELETE"]
    assert str(azure.pedidos[-1].url) == RESULTADO  # o resultado é apagado no fim


def test_sem_configuracao_nao_faz_pedidos():
    def handler(request):
        raise AssertionError("não devia ter feito nenhum pedido")

    with pytest.raises(OCRNaoConfigurado):
        ler(handler, env={k: v for k, v in ENV.items() if "DOCINTEL" not in k})


def test_nunca_envia_a_chave_para_outro_servidor():
    azure = AzureFalso(operacao="https://servidor-estranho.example/resultado")
    with pytest.raises(ErroOCR):
        ler(azure)
    assert all(p.url.host == "clarity-ocr.cognitiveservices.azure.com" for p in azure.pedidos)


@pytest.mark.parametrize(
    ("primeiro", "codigo"),
    [
        (httpx.Response(401), 502),
        (httpx.Response(404), 502),
        (httpx.Response(429), 429),
        (httpx.Response(400, json={"error": {"message": TEXTO}}), 422),
        (httpx.Response(500, text=TEXTO), 502),
    ],
)
def test_erros_do_azure_viram_mensagens_sem_dados(primeiro, codigo):
    with pytest.raises(ErroOCR) as erro:
        ler(AzureFalso(primeiro=primeiro))
    assert erro.value.codigo == codigo
    assert TEXTO not in str(erro.value)
    assert CHAVE not in str(erro.value)


def test_leitura_falhada_e_apagada_na_mesma():
    azure = AzureFalso(resposta_final={"status": "failed", "error": {"message": TEXTO}})
    with pytest.raises(ErroOCR) as erro:
        ler(azure)
    assert erro.value.codigo == 422
    assert azure.pedidos[-1].method == "DELETE"


def test_desiste_se_demorar_demasiado(monkeypatch):
    monkeypatch.setattr(modulo_ocr, "TENTATIVAS", 3)
    azure = AzureFalso(resposta_final={"status": "running"})
    with pytest.raises(ErroOCR) as erro:
        ler(azure)
    assert erro.value.codigo == 504
    assert azure.pedidos[-1].method == "DELETE"


def test_sem_rede():
    def sem_rede(request):
        raise httpx.ConnectError("sem rede", request=request)

    with pytest.raises(ErroOCR) as erro:
        ler(sem_rede)
    assert erro.value.codigo == 502


# Endpoint /api/ocr/notas


class LeitorFalso:
    def __init__(self, texto=TEXTO):
        self.texto = texto
        self.imagens: list[tuple[bytes, str]] = []
        self.erro: ErroOCR | None = None

    async def __call__(self, _client, _settings, imagem, tipo):
        self.imagens.append((imagem, tipo))
        if self.erro is not None:
            raise self.erro
        return self.texto


@pytest.fixture
def leitor():
    return LeitorFalso()


@pytest.fixture
def api(leitor):
    usar_supabase(SupabaseFalso())
    app.dependency_overrides[get_leitor] = lambda: leitor
    yield TestClient(app)
    app.dependency_overrides.clear()


def enviar(api, conteudo=IMAGEM, tipo="image/jpeg", headers=ANA):
    return api.post("/api/ocr/notas", content=conteudo, headers={**headers, "Content-Type": tipo})


def test_devolve_o_texto_lido(api, leitor):
    res = enviar(api)
    assert res.status_code == 200, res.text
    assert res.json() == {"texto": TEXTO}
    assert leitor.imagens == [(IMAGEM, "image/jpeg")]


def test_exige_sessao(api, leitor):
    assert enviar(api, headers={}).status_code == 401
    assert enviar(api, headers={"Authorization": "Bearer token-invalido"}).status_code == 401
    assert leitor.imagens == []


@pytest.mark.parametrize(
    "tipo", ["text/plain", "application/json", "application/msword", "image/gif", ""]
)
def test_recusa_outros_tipos(api, leitor, tipo):
    assert enviar(api, tipo=tipo).status_code == 415
    assert leitor.imagens == []


@pytest.mark.parametrize("tipo", ["image/png", "application/pdf", DOCX])
def test_aceita_png_pdf_e_docx(api, leitor, tipo):
    assert enviar(api, tipo=tipo).status_code == 200
    assert leitor.imagens == [(IMAGEM, tipo)]


def test_recusa_imagens_grandes_e_vazias(api, leitor):
    assert enviar(api, conteudo=b"x" * (TAMANHO_MAXIMO + 1)).status_code == 413
    assert enviar(api, conteudo=b"").status_code == 422
    assert leitor.imagens == []


def test_sem_texto_na_imagem_da_422(api, leitor):
    leitor.texto = ""
    res = enviar(api)
    assert res.status_code == 422
    assert "texto" in res.json()["detail"]


@pytest.mark.parametrize("codigo", [422, 429, 502, 504])
def test_erros_do_ocr_chegam_a_app(api, leitor, codigo):
    leitor.erro = ErroOCR("Mensagem para o psicólogo.", codigo)
    res = enviar(api)
    assert res.status_code == codigo
    assert res.json()["detail"] == "Mensagem para o psicólogo."


def test_sem_ocr_configurado_da_503(api):
    # Sem substituir o leitor: os testes não têm variáveis AZURE_DOCINTEL_*.
    app.dependency_overrides.pop(get_leitor)
    assert enviar(api).status_code == 503
