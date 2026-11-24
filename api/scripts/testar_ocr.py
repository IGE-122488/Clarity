"""Testa a leitura de uma fotografia, PDF ou .docx com o Azure Document Intelligence.

Usa os valores do api/.env.

Como correr, dentro da pasta api/ com o ambiente virtual ativo:

    python scripts/testar_ocr.py caminho\\para\\o\\ficheiro.jpg

Use só ficheiros de notas FICTÍCIAS. Mostra o texto lido; nunca mostra a chave.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import read_settings  # noqa: E402
from app.ocr import DOCX, TAMANHO_MAXIMO, ErroOCR, OCRNaoConfigurado, ler_texto  # noqa: E402
from scripts.testar_ia import ler_env  # noqa: E402


async def main() -> int:
    escrever = sys.stdout.write
    if len(sys.argv) != 2:
        escrever("Uso: python scripts/testar_ocr.py caminho\\para\\a\\foto.jpg\n")
        return 1
    foto = Path(sys.argv[1])
    tipo = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".pdf": "application/pdf",
        ".docx": DOCX,
    }.get(foto.suffix.lower())
    if not foto.exists() or tipo is None:
        escrever("FALHOU: indique um ficheiro .jpg, .png, .pdf ou .docx que exista.\n")
        return 1
    imagem = foto.read_bytes()
    if len(imagem) > TAMANHO_MAXIMO:
        escrever("FALHOU: o ficheiro tem mais de 4 MB (a app reduz as fotografias; aqui não).\n")
        return 1

    env = {**os.environ, **ler_env(Path(__file__).resolve().parents[1] / ".env")}
    settings = read_settings(env)
    escrever(f"Endereço: {settings.ocr_endpoint}\n")
    try:
        async with httpx.AsyncClient() as client:
            texto = await ler_texto(client, settings, imagem, tipo)
    except OCRNaoConfigurado:
        escrever("FALHOU: faltam AZURE_DOCINTEL_ENDPOINT ou AZURE_DOCINTEL_KEY no api/.env\n")
        return 1
    except ErroOCR as erro:
        escrever(f"FALHOU ({erro.codigo}): {erro}\n")
        return 1
    escrever(f"Texto lido:\n{texto or '(nenhum)'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
