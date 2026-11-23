"""Ligação ao modelo de IA (Azure OpenAI, API "Responses" v1).

Usa o mesmo httpx do resto da API: não precisa de bibliotecas novas.

Privacidade:
- `store: false` pede ao Azure que não guarde o pedido nem a resposta.
- Os erros nunca incluem o texto enviado nem a resposta do Azure (podem conter dados de pacientes).
- A chave vai só no cabeçalho `api-key` e nunca aparece em mensagens de erro.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings

TEMPO_MAXIMO = 90.0  # segundos: os modelos "mini" que raciocinam podem demorar uns segundos


class IANaoConfigurada(Exception):
    """Faltam as variáveis AZURE_OPENAI_* (→ 503)."""


class ErroIA(Exception):
    """O serviço de IA falhou ou recusou o pedido. `codigo` é o código HTTP a devolver à app."""

    def __init__(self, mensagem: str, codigo: int = 502) -> None:
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass(frozen=True)
class RespostaIA:
    texto: str
    modelo: str


def _extrair_texto(dados: dict[str, Any]) -> str:
    """Junta os blocos `output_text` das mensagens da resposta (ignora o raciocínio interno)."""
    partes = [
        bloco.get("text", "")
        for item in dados.get("output") or []
        if item.get("type") == "message"
        for bloco in item.get("content") or []
        if bloco.get("type") == "output_text"
    ]
    return "".join(partes).strip()


def _filtro_de_conteudo(res: httpx.Response) -> bool:
    try:
        erro = res.json().get("error") or {}
    except ValueError:
        return False
    return "content_filter" in str(erro.get("code", "")) or "content_filter" in str(
        erro.get("innererror", "")
    )


async def gerar_texto(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    instrucoes: str,
    entrada: str,
    max_tokens: int = 4000,
) -> RespostaIA:
    """Pede um texto ao modelo. `max_tokens` inclui o raciocínio interno do modelo."""
    if not settings.ia_configurada:
        raise IANaoConfigurada("O serviço de IA não está configurado.")

    corpo = {
        "model": settings.ia_deployment,
        "instructions": instrucoes,
        "input": entrada,
        "max_output_tokens": max_tokens,
        "reasoning": {"effort": "low"},
        "store": False,
    }
    try:
        res = await client.post(
            f"{settings.ia_base_url}/responses",
            json=corpo,
            headers={"api-key": settings.ia_api_key or ""},
            timeout=TEMPO_MAXIMO,
        )
    except httpx.TimeoutException as exc:
        raise ErroIA("O serviço de IA demorou demasiado a responder. Tente de novo.", 504) from exc
    except httpx.HTTPError as exc:
        raise ErroIA("Sem ligação ao serviço de IA. Tente de novo.") from exc

    if res.status_code in (401, 403):
        raise ErroIA("O serviço de IA recusou a chave. Verifiquem AZURE_OPENAI_API_KEY.")
    if res.status_code == 404:
        raise ErroIA("Implementação de IA não encontrada. Verifiquem AZURE_OPENAI_DEPLOYMENT.")
    if res.status_code == 429:
        raise ErroIA("O serviço de IA está ocupado. Tente daqui a um minuto.", 429)
    if res.status_code == 400 and _filtro_de_conteudo(res):
        raise ErroIA(
            "O filtro de conteúdo do Azure bloqueou o pedido (as notas tocam em temas sensíveis).",
            422,
        )
    if res.status_code >= 400:
        raise ErroIA(f"O serviço de IA respondeu com o código {res.status_code}.")

    dados = res.json()
    texto = _extrair_texto(dados)
    if dados.get("status") == "incomplete" or not texto:
        raise ErroIA("A IA não conseguiu terminar o texto. Tente de novo.")
    return RespostaIA(texto=texto, modelo=str(dados.get("model") or settings.ia_deployment))
