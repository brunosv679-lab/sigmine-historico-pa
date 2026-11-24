"""
Configuração da aplicação — leitura segura do .env via python-dotenv.
Nenhuma credencial é hardcoded aqui.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY: str = os.environ["FLASK_SECRET_KEY"]
    DEBUG: bool = os.getenv("FLASK_ENV", "production") == "development"

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI: str = (
        f"postgresql+psycopg2://"
        f"{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
        f"/{os.environ['DB_NAME']}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ETL
    ANM_PA_URL: str = os.getenv(
        "ANM_PA_URL",
        "https://dadosabertos.anm.gov.br/SIGMINE/PROCESSOS_MINERARIOS/PA.zip",
    )
    DATA_RAW_DIR: str = os.getenv("DATA_RAW_DIR", "data/raw")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
