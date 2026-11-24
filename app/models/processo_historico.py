"""
Model — ProcessoHistorico
Consultas de linha do tempo SCD Tipo 2 de um processo minerário.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy import text, bindparam
from app.extensions import db


def get_historico_processo(numero_processo: str) -> list[dict]:
    """
    Retorna a linha do tempo completa de um processo (SCD Tipo 2),
    ordenada cronologicamente.
    """
    sql = text("""
        SELECT
            id,
            numero_processo,
            fase,
            ult_evento,
            area_ha,
            substancia,
            tipo_mudanca,
            valido_de::text,
            valido_ate::text,
            ST_AsGeoJSON(ST_Transform(geom, 4326), 6)::json AS geometry
        FROM processos_historico
        WHERE numero_processo = :np
        ORDER BY valido_de ASC
    """).bindparams(bindparam("np", value=numero_processo))

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_novos_por_mes(meses: int = 24) -> list[dict]:
    """
    Agrega novos requerimentos por mês nos últimos N meses.
    Retorna lista [{mes, total}] para gráficos.
    """
    sql = text("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', valido_de), 'YYYY-MM') AS mes,
            COUNT(*) AS total
        FROM processos_historico
        WHERE tipo_mudanca = 'NOVO'
          AND valido_de >= NOW() - INTERVAL '1 month' * :meses
        GROUP BY DATE_TRUNC('month', valido_de)
        ORDER BY DATE_TRUNC('month', valido_de)
    """).bindparams(bindparam("meses", value=meses))

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_mudancas_por_tipo(meses: int = 12) -> list[dict]:
    """Agrega mudanças por tipo no período."""
    sql = text("""
        SELECT
            tipo_mudanca,
            COUNT(*) AS total
        FROM processos_historico
        WHERE valido_de >= NOW() - INTERVAL '1 month' * :meses
        GROUP BY tipo_mudanca
        ORDER BY total DESC
    """).bindparams(bindparam("meses", value=meses))

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_novos_por_substancia(meses: int = 12) -> list[dict]:
    """Agrega novos requerimentos por substância no período."""
    sql = text("""
        SELECT
            COALESCE(substancia, 'Não informado') AS substancia,
            COUNT(*) AS total
        FROM processos_historico
        WHERE tipo_mudanca = 'NOVO'
          AND valido_de >= NOW() - INTERVAL '1 month' * :meses
        GROUP BY substancia
        ORDER BY total DESC
        LIMIT 20
    """).bindparams(bindparam("meses", value=meses))

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]


def get_dinamica_espacial(tipo_mudanca: str = "NOVO") -> list[dict]:
    """
    Retorna geometrias de processos com determinado tipo de mudança
    para o mapa de dinâmica.
    """
    sql = text("""
        SELECT
            h.numero_processo,
            h.fase,
            h.substancia,
            h.tipo_mudanca,
            h.valido_de::text,
            ST_AsGeoJSON(ST_Transform(h.geom, 4326), 6)::json AS geometry
        FROM processos_historico h
        WHERE h.tipo_mudanca = :tipo
          AND h.valido_de >= NOW() - INTERVAL '6 months'
          AND h.geom IS NOT NULL
        ORDER BY h.valido_de DESC
        LIMIT 500
    """).bindparams(bindparam("tipo", value=tipo_mudanca))

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(r) for r in rows]
