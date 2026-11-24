"""
Service — Spatial Cleaner
Validação geométrica (make_valid), encoding cp1252 → utf-8 e reprojeção para SRID 4674.
Lê o shapefile com Fiona, valida com Shapely e carrega na tabela processos_staging.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import fiona
from fiona import Feature
from shapely.geometry import shape, mapping, MultiPolygon, Polygon
try:
    from shapely import make_valid
except ImportError:
    from shapely.validation import make_valid
from sqlalchemy import text
from app.extensions import db

logger = logging.getLogger(__name__)

# Mapeamento de campos do shapefile ANM → colunas do banco
FIELD_MAP = {
    "PROCESSO":    "numero_processo",
    "NOME":        "nome",
    "FASE":        "fase",
    "ULT_EVENTO":  "ult_evento",
    "ULT_EVE_DA":  "ult_eve_data",
    "AREA_HA":     "area_ha",
    "SUBS":        "substancia",
    "USO":         "uso_solo",
    "TIPO":        "tipo_requerimento",
    "MUNICIPIOS":  "municipio",
    "UF":          "uf",
    "ID":          "id_original",
}

TARGET_SRID = 4674  # SIRGAS 2000


def _decode_field(value) -> str | None:
    """Decodifica campos que podem vir como bytes cp1252."""
    if isinstance(value, bytes):
        return value.decode("cp1252", errors="replace")
    return value


def _to_multipolygon(geom_shape) -> MultiPolygon | None:
    """Garante que a geometria seja um MultiPolygon válido."""
    if geom_shape is None or geom_shape.is_empty:
        return None
    if not geom_shape.is_valid:
        geom_shape = make_valid(geom_shape)
    if isinstance(geom_shape, Polygon):
        geom_shape = MultiPolygon([geom_shape])
    elif not isinstance(geom_shape, MultiPolygon):
        # Tenta converter (ex: GeometryCollection com polígonos)
        polys = [g for g in getattr(geom_shape, "geoms", []) if isinstance(g, (Polygon, MultiPolygon))]
        if not polys:
            return None
        from shapely.ops import unary_union
        geom_shape = unary_union(polys)
        if isinstance(geom_shape, Polygon):
            geom_shape = MultiPolygon([geom_shape])
    return geom_shape if isinstance(geom_shape, MultiPolygon) else None


def iter_features_from_shapefile(shp_path: Path) -> Iterator[dict]:
    """
    Itera sobre as feições do shapefile, aplicando:
    - Decodificação cp1252 → str
    - Validação e correção de geometria (make_valid)
    - Conversão para MultiPolygon
    Yields dicts com campos mapeados + wkt da geometria.
    """
    encoding = "cp1252"
    total = 0
    skipped = 0

    with fiona.open(str(shp_path), encoding=encoding) as src:
        logger.info(
            "Shapefile: %d feições | CRS: %s",
            len(src),
            src.crs.to_epsg() if src.crs else "desconhecido",
        )
        for feat in src:
            props = feat["properties"]
            raw_geom = feat.get("geometry")

            if raw_geom is None:
                skipped += 1
                continue

            geom_shape = _to_multipolygon(shape(raw_geom))
            if geom_shape is None:
                skipped += 1
                continue

            record = {
                col: _decode_field(props.get(src_field))
                for src_field, col in FIELD_MAP.items()
            }
            record["geom_wkt"] = geom_shape.wkt
            total += 1
            yield record

    logger.info("Feições processadas: %d | Ignoradas: %d", total, skipped)


def load_staging(shp_path: Path, execucao_id: int) -> int:
    """
    Trunca a tabela staging e carrega os dados do shapefile.

    Returns:
        Número de registros carregados.
    """
    inserted = 0
    batch: list[dict] = []
    BATCH_SIZE = 500

    def flush_batch(batch: list[dict], conn) -> int:
        if not batch:
            return 0
        conn.execute(
            text("""
                INSERT INTO processos_staging (
                    numero_processo, nome, fase, ult_evento, ult_eve_data,
                    area_ha, substancia, uso_solo, tipo_requerimento,
                    municipio, uf, id_original, geom
                ) VALUES (
                    :numero_processo, :nome, :fase, :ult_evento,
                    CAST(NULLIF(:ult_eve_data, '') AS DATE),
                    CAST(:area_ha AS NUMERIC), :substancia, :uso_solo,
                    :tipo_requerimento, :municipio, :uf,
                    :id_original,
                    ST_Force2D(ST_Multi(ST_GeomFromText(:geom_wkt, 4674)))
                )
            """),
            batch,
        )
        return len(batch)

    with db.engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE processos_staging"))
        logger.info("Tabela staging truncada.")

        for record in iter_features_from_shapefile(shp_path):
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                inserted += flush_batch(batch, conn)
                batch = []
                logger.debug("Staging: %d registros inseridos…", inserted)

        inserted += flush_batch(batch, conn)

    logger.info("Total inserido no staging: %d", inserted)
    return inserted
