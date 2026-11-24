"""
Controller — API Controller
API REST/GeoJSON para consumo pelo frontend Leaflet.

Endpoints:
  GET /api/processos?bbox=min_lon,min_lat,max_lon,max_lat[&fase=...][&substancia=...]
  GET /api/historico/<numero_processo>
  GET /api/dinamica?tipo=NOVO|FASE|TITULAR|GEOMETRIA|REMOVIDO
  GET /api/stats/novos-por-mes?meses=24
  GET /api/stats/por-substancia?meses=12
  GET /api/stats/mudancas?meses=12
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, abort

from app.models.processo_atual import (
    get_processos_por_bbox,
    get_processo_by_numero,
    get_total_count,
)
from app.models.processo_historico import (
    get_historico_processo,
    get_novos_por_mes,
    get_novos_por_substancia,
    get_mudancas_por_tipo,
    get_dinamica_espacial,
)
from app.models.etl_log import get_ultimas_execucoes

api_bp = Blueprint("api", __name__)

TIPOS_MUDANCA_VALIDOS = {"NOVO", "FASE", "TITULAR", "GEOMETRIA", "REMOVIDO"}


def _build_geojson(features: list[dict]) -> dict:
    """Monta uma FeatureCollection GeoJSON a partir de dicts do banco."""
    fc_features = []
    for row in features:
        geom = row.pop("geometry", None)
        if geom is None:
            continue
        fc_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {k: v for k, v in row.items()},
        })
    return {"type": "FeatureCollection", "features": fc_features}


@api_bp.route("/processos")
def get_processos():
    """
    Retorna processos em um bounding-box como GeoJSON.
    Query params: bbox=min_lon,min_lat,max_lon,max_lat (obrigatório)
                  fase, substancia (opcionais)
                  limit (padrão 2000)
    """
    bbox_str = request.args.get("bbox")
    if not bbox_str:
        abort(400, "Parâmetro 'bbox' é obrigatório: min_lon,min_lat,max_lon,max_lat")

    try:
        parts = [float(x) for x in bbox_str.split(",")]
        if len(parts) != 4:
            raise ValueError("bbox deve ter exatamente 4 valores")
        min_lon, min_lat, max_lon, max_lat = parts
    except ValueError as exc:
        abort(400, f"bbox inválido: {exc}")

    fase = request.args.get("fase")
    substancia = request.args.get("substancia")
    limit = min(int(request.args.get("limit", 2000)), 5000)

    rows = get_processos_por_bbox(min_lon, min_lat, max_lon, max_lat, fase, substancia, limit)
    geojson = _build_geojson(rows)
    return jsonify(geojson)


@api_bp.route("/historico/<path:numero_processo>")
def get_historico(numero_processo: str):
    """Retorna a linha do tempo SCD Tipo 2 de um processo como GeoJSON."""
    rows = get_historico_processo(numero_processo)
    if not rows:
        abort(404, f"Processo '{numero_processo}' não encontrado no histórico")
    geojson = _build_geojson(rows)
    return jsonify(geojson)


@api_bp.route("/processo/<path:numero_processo>")
def get_processo(numero_processo: str):
    """Retorna detalhes de um processo específico."""
    row = get_processo_by_numero(numero_processo)
    if not row:
        abort(404, f"Processo '{numero_processo}' não encontrado")
    geom = row.pop("geometry", None)
    return jsonify({
        "type": "Feature",
        "geometry": geom,
        "properties": row,
    })


@api_bp.route("/dinamica")
def get_dinamica():
    """
    Retorna geometrias de processos com determinado tipo de mudança (últimos 6 meses).
    Query param: tipo (padrão: NOVO)
    """
    tipo = request.args.get("tipo", "NOVO").upper()
    if tipo not in TIPOS_MUDANCA_VALIDOS:
        abort(400, f"Tipo inválido. Use: {', '.join(TIPOS_MUDANCA_VALIDOS)}")

    rows = get_dinamica_espacial(tipo)
    geojson = _build_geojson(rows)
    return jsonify(geojson)


@api_bp.route("/stats/novos-por-mes")
def stats_novos_por_mes():
    """Agrega novos requerimentos por mês."""
    meses = int(request.args.get("meses", 24))
    data = get_novos_por_mes(meses)
    return jsonify({"data": [dict(r) for r in data]})


@api_bp.route("/stats/por-substancia")
def stats_por_substancia():
    """Agrega novos requerimentos por substância."""
    meses = int(request.args.get("meses", 12))
    data = get_novos_por_substancia(meses)
    return jsonify({"data": [dict(r) for r in data]})


@api_bp.route("/stats/mudancas")
def stats_mudancas():
    """Agrega mudanças por tipo no período."""
    meses = int(request.args.get("meses", 12))
    data = get_mudancas_por_tipo(meses)
    return jsonify({"data": [dict(r) for r in data]})


@api_bp.route("/etl/execucoes")
def etl_execucoes():
    """Retorna as últimas execuções ETL para monitoramento."""
    limit = int(request.args.get("limit", 10))
    data = get_ultimas_execucoes(limit)
    return jsonify({"execucoes": data})


@api_bp.route("/status")
def api_status():
    """Status geral da API."""
    total = get_total_count()
    return jsonify({
        "status": "online",
        "total_processos": total,
        "version": "1.0.0",
    })
