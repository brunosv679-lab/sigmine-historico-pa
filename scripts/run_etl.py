#!/usr/bin/env python3
"""
CLI agendável no cron diário para executar o pipeline ETL.
Uso:
  python scripts/run_etl.py [--force-download] [--backfill-demo]

Configurar no cron:
  0 3 * * * /home/nathan/sigmine-historico-pa/venv/bin/python \
      /home/nathan/sigmine-historico-pa/scripts/run_etl.py >> \
      /home/nathan/sigmine-historico-pa/logs/etl.log 2>&1
"""
import sys
import os
import logging
import argparse

# Adiciona o diretório raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.services.etl_runner import run_pipeline, run_backfill_demo

# Configuração de logging
LOG_DIR = os.getenv("LOG_DIR", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "etl.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("run_etl")


def parse_args():
    parser = argparse.ArgumentParser(description="Pipeline ETL — SIGMINE PA")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Força novo download mesmo se o arquivo já existir",
    )
    parser.add_argument(
        "--backfill-demo",
        action="store_true",
        help="Injeta dados históricos sintéticos para demonstração",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        if args.backfill_demo:
            logger.info("Executando backfill demo…")
            run_backfill_demo(app)
        else:
            logger.info("Executando pipeline ETL completo…")
            result = run_pipeline(force_download=args.force_download)
            logger.info("Resultado: %s", result)
            if result.get("status") != "SUCCESS":
                sys.exit(1)


if __name__ == "__main__":
    main()
