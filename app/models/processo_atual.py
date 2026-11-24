"""
Model — ProcessoAtual
Consultas à tabela processos_atual usando SQLAlchemy com bindparams
(prevenção de SQL Injection). Nenhum SQL literal concatenado.
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy import text, bindparam
from app.extensions import db


def get_processos_por_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    fase: Optional[str] = None,
    substancia: Optional[str] = None,
    limit: int = 2000,
) -> list[dict]:
    """
    Retorna processos dentro de um bounding-box como lista de dicts GeoJSON-ready.
    Todos os parâmetros são vinculados (bindparams) — nenhuma interpolação de string.
    """
    bbox_wkt = f"POLYGON(({min_lon} {min_lat},{max_lon} {min_lat},{max_lon} {max_lat},{min_lon} {max_lat},{min_lon} {min_lat}))"

    sql = text("""
        SELECT
            numero_processo,
            nome,
            fase,
            ult_evento,
            ult_eve_data::text,
            area_ha,
            substancia,
            municipio,
            atualizado_em::text,
            ST_AsGeoJSON(geom, 6)::json AS geometry
        FROM processos_atual
        WHERE ST_Intersects(
            geom,
            ST_GeomFromText(:bbox_wkt, 4674)
        )
        AND (:fase IS NULL OR fase = :fase)
        AND (:substancia IS NULL OR substancia ILIKE :substancia_like)
        ORDER BY area_ha DESC NULLS LAST
        LIMIT :lim
    """).bindparams(
        bindparam("bbox_wkt", value=bbox_wkt),
        bindparam("fase", value=fase),
        bindparam("substancia", value=substancia),
        bindparam("substancia_like", value=f"%{substancia}%" if substancia else None),
        bindparam("lim", value=limit),
    )

    with db.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(r) for r in rows]


def get_processo_by_numero(numero_processo: str) -> Optional[dict]:
    """Retorna um processo pelo número exato."""
    sql = text("""
        SELECT
            numero_processo, nome, fase, ult_evento,
            ult_eve_data::text, area_ha, substancia,
            uso_solo, tipo_requerimento, municipio, uf,
            criado_em::text, atualizado_em::text,
            ST_AsGeoJSON(geom, 6)::json AS geometry
        FROM processos_atual
        WHERE numero_processo = :np
    """).bindparams(bindparam("np", value=numero_processo))

    with db.engine.connect() as conn:
        row = conn.execute(sql).mappings().first()

    return dict(row) if row else None


def get_total_count() -> int:
    """Conta total de processos ativos."""
    with db.engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM processos_atual")).scalar()


def get_fases_disponiveis() -> list[str]:
    """Lista todas as fases distintas."""
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT fase FROM processos_atual WHERE fase IS NOT NULL ORDER BY fase")
        ).scalars().all()
    return list(rows)


def get_substancias_disponiveis() -> list[str]:
    """Lista todas as substâncias distintas."""
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT substancia FROM processos_atual WHERE substancia IS NOT NULL ORDER BY substancia")
        ).scalars().all()
    return list(rows)
