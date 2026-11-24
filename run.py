#!/usr/bin/env python3
"""
Entrypoint exclusivo do servidor Flask.
Em produção use Gunicorn via sigmine.service.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    import os
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 8001)),
        debug=os.getenv("FLASK_ENV") == "development",
    )
