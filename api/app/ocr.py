"""Leitura de notas a partir de uma fotografia, PDF ou Word (Azure Document Intelligence, "Read").

Lê manuscrito em fotografias e PDFs digitalizados, e o texto de PDFs digitais e de .docx.

Usa o mesmo httpx do resto da API: não precisa de bibliotecas novas.

Privacidade:
- O ficheiro e o texto lido NÃO ficam guardados na nossa API nem na base de dados: o texto
  volta para o browser, o psicólogo revê-o e só fica guardado se o acrescentar às notas.
- No fim pedimos ao Azure que apague o resultado da leitura (senão fica lá até 24 horas).
- Os erros nunca incluem o ficheiro, o texto nem a resposta do Azure.
"""

import asyncio
from urllib.parse import urlparse

import httpx

from .config import Settings

API_VERSION = "2024-11-30"
TAMANHO_MAXIMO = 4 * 1024 * 1024  # limite do plano gratuito (F0), que lê só as 2 primeiras páginas
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TIPOS_ACEITES = {"image/jpeg", "image/png", "application/pdf", DOCX}
TENTATIVAS = 30  # a leitura demora normalmente 1 a 5 s; desiste ao fim de ~30 s


class OCRNaoConfigurado(Exception):
    """Faltam as variáveis AZURE_DOCINTEL_* (→ 503)."""


class ErroOCR(Exception):
    """O serviço de OCR falhou ou recusou a imagem. `codigo` é o código HTTP a devolver à app."""

    def __init__(self, mensagem: str, codigo: int = 502) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


def _erro_do_pedido(res: httpx.Response) -> ErroOCR | None:
    if res.status_code in (401, 403):
        return ErroOCR("O serviço de OCR recusou a chave. Verifiquem AZURE_DOCINTEL_KEY.")
    if res.status_code == 404:
        return ErroOCR("Serviço de OCR não encontrado. Verifiquem AZURE_DOCINTEL_ENDPOINT.")
    if res.status_code == 429:
        return ErroOCR("O serviço de OCR está ocupado. Tente daqui a um minuto.", 429)
    if res.status_code in (400, 415):
        return ErroOCR(
            "Não foi possível ler este ficheiro. Tente outra fotografia, um PDF ou um .docx.", 422
        )
    if res.status_code >= 400:
        return ErroOCR(f"O serviço de OCR respondeu com o código {res.status_code}.")
    return None


async def ler_texto(
    client: httpx.AsyncClient,
    settings: Settings,
    imagem: bytes,
    tipo: str,
    *,
    espera: float = 1.0,
) -> str:
    """Devolve o texto lido no ficheiro (vazio se não houver texto)."""
    if not settings.ocr_configurado:
        raise OCRNaoConfigurado("O serviço de OCR não está configurado.")

    chave = {"Ocp-Apim-Subscription-Key": settings.ocr_key or ""}
    url = (
        f"{settings.ocr_endpoint}/documentintelligence/documentModels/prebuilt-read:analyze"
        f"?api-version={API_VERSION}"
    )
    try:
        res = await client.post(
            url, content=imagem, headers={**chave, "Content-Type": tipo}, timeout=30.0
        )
    except httpx.HTTPError as exc:
        raise ErroOCR("Sem ligação ao serviço de OCR. Tente de novo.") from exc
    if (erro := _erro_do_pedido(res)) is not None:
        raise erro

    resultado = res.headers.get("operation-location", "")
    # Só enviamos a chave para o mesmo servidor do Azure que configurámos.
    if urlparse(resultado).netloc != urlparse(settings.ocr_endpoint).netloc:
        raise ErroOCR("Resposta inesperada do serviço de OCR.")

    try:
        for _ in range(TENTATIVAS):
            await asyncio.sleep(espera)
            try:
                res = await client.get(resultado, headers=chave, timeout=15.0)
            except httpx.HTTPError as exc:
                raise ErroOCR("Sem ligação ao serviço de OCR. Tente de novo.") from exc
            if (erro := _erro_do_pedido(res)) is not None:
                raise erro
            dados = res.json()
            estado = dados.get("status")
            if estado == "succeeded":
                return str((dados.get("analyzeResult") or {}).get("content") or "").strip()
            if estado == "failed":
                raise ErroOCR("O Azure não conseguiu ler este ficheiro. Tente outro.", 422)
        raise ErroOCR("A leitura demorou demasiado. Tente de novo.", 504)
    finally:
        # Apagar o resultado no Azure. Se falhar, o Azure apaga-o sozinho em 24 horas.
        try:
            await client.delete(resultado, headers=chave, timeout=10.0)
        except httpx.HTTPError:
            pass
