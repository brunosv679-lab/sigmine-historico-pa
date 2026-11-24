"""
Instâncias de extensões Flask (SQLAlchemy/GeoAlchemy2).
Importadas pela factory para evitar importações circulares.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
