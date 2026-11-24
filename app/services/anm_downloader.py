"""
Service — ANM Downloader
Download real do shapefile de processos minerários do Pará da ANM.
URL: https://dadosabertos.anm.gov.br/SIGMINE/PROCESSOS_MINERARIOS/PA.zip
"""
from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ANM_PA_URL = os.getenv(
    "ANM_PA_URL",
    "https://dadosabertos.anm.gov.br/SIGMINE/PROCESSOS_MINERARIOS/PA.zip",
)
DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", "data/raw"))


def download_pa_zip(force: bool = False) -> Path:
    """
    Faz o download do arquivo PA.zip da ANM.

    Args:
        force: Se True, re-baixa mesmo que o arquivo já exista.

    Returns:
        Caminho absoluto do arquivo .zip baixado.
    """
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_RAW_DIR / "PA.zip"

    if zip_path.exists() and not force:
        logger.info("Arquivo %s já existe, pulando download.", zip_path)
        return zip_path

    logger.info("Iniciando download de %s …", ANM_PA_URL)
    try:
        with requests.get(ANM_PA_URL, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        logger.debug("Download: %.1f%%", pct)
        logger.info("Download concluído: %s (%.1f MB)", zip_path, zip_path.stat().st_size / 1e6)
    except requests.RequestException as exc:
        logger.error("Falha no download: %s", exc)
        raise

    return zip_path


def extract_pa_zip(zip_path: Path, overwrite: bool = False) -> Path:
    """
    Extrai o arquivo PA.zip no subdiretório data/raw/PA/.

    Returns:
        Caminho do diretório extraído.
    """
    extract_dir = DATA_RAW_DIR / "PA"
    shp_candidates = list(extract_dir.glob("*.shp"))

    if shp_candidates and not overwrite:
        logger.info("Shapefile já extraído em %s", extract_dir)
        return extract_dir

    extract_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Extraindo %s → %s", zip_path, extract_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    shp_files = list(extract_dir.glob("**/*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Nenhum shapefile encontrado em {extract_dir}")

    logger.info("Shapefile extraído: %s", shp_files[0])
    return extract_dir


def find_shapefile(extract_dir: Path) -> Path:
    """Localiza o primeiro .shp no diretório extraído."""
    shp_files = list(extract_dir.glob("**/*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Nenhum shapefile encontrado em {extract_dir}")
    return shp_files[0]


def download_and_extract(force_download: bool = False) -> Path:
    """Conveniência: baixa e extrai, retorna o caminho do .shp."""
    zip_path = download_pa_zip(force=force_download)
    extract_dir = extract_pa_zip(zip_path)
    return find_shapefile(extract_dir)
