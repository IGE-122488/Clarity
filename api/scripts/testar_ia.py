"""Testa a ligação ao Azure OpenAI com os valores do api/.env (sem dados de pacientes).

Como correr, dentro da pasta api/ com o ambiente virtual ativo:

    python scripts/testar_ia.py

Envia uma frase fictícia e mostra se a chave, o endereço e o nome da implementação estão certos.
Nunca mostra a chave.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import read_settings  # noqa: E402
from app.ia import ErroIA, IANaoConfigurada, gerar_texto  # noqa: E402


def ler_env(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                nome, valor = linha.split("=", 1)
                valores[nome.strip()] = valor.strip().strip('"').strip("'")
    return valores


async def main() -> int:
    env = {**os.environ, **ler_env(Path(__file__).resolve().parents[1] / ".env")}
    settings = read_settings(env)
    escrever = sys.stdout.write
    escrever(f"Endereço: {settings.ia_base_url}\nImplementação: {settings.ia_deployment}\n")
    try:
        async with httpx.AsyncClient() as client:
            resposta = await gerar_texto(
                client,
                settings,
                instrucoes="Responde só com a frase pedida.",
                entrada="Escreve exatamente: Ligação ao Clarity OK.",
                max_tokens=500,
            )
    except IANaoConfigurada:
        escrever("FALHOU: faltam AZURE_OPENAI_BASE_URL, _API_KEY ou _DEPLOYMENT no api/.env\n")
        return 1
    except ErroIA as erro:
        escrever(f"FALHOU ({erro.codigo}): {erro}\n")
        return 1
    escrever(f"Modelo: {resposta.modelo}\nResposta: {resposta.texto}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
