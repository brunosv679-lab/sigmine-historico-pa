"""
Service — Change Detector
Detecta mudanças entre staging (novo download) e processos_atual (snapshot anterior).
Implementa SCD Tipo 2: registra cada mudança com valido_de/valido_ate.

Tipos de mudança detectados:
  NOVO       — processo não existia antes
  FASE       — mudança de fase do processo
  TITULAR    — mudança de titular/nome
  GEOMETRIA  — deslocamento espacial detectado (ST_SnapToGrid para ruído)
  REMOVIDO   — processo sumiu do shapefile ANM
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import text
from app.extensions import db

logger = logging.getLogger(__name__)

NOW_UTC = datetime.now(tz=timezone.utc)

# Tolerância para comparação de geometrias (SnapToGrid em graus ≈ ~1m)
SNAP_GRID = 0.00001


def detect_and_apply_changes(execucao_id: int) -> dict[str, int]:
    """
    Compara staging com processos_atual e aplica mudanças:
    - Insere novos em processos_atual e histórico
    - Atualiza mudanças em processos_atual e histórico (SCD2)
    - Registra removidos no histórico

    Returns:
        Dict com contagens: {novos, atualizados, removidos}
    """
    contagens = {"novos": 0, "atualizados": 0, "removidos": 0}

    with db.engine.begin() as conn:
        # --- 1. PROCESSOS NOVOS ---
        novos = conn.execute(text("""
            SELECT s.*
            FROM processos_staging s
            LEFT JOIN processos_atual a ON a.numero_processo = s.numero_processo
            WHERE a.id IS NULL
        """)).mappings().all()

        for row in novos:
            _insert_atual(conn, row)
            _insert_historico(conn, row, "NOVO", execucao_id)
            contagens["novos"] += 1

        logger.info("Novos processos: %d", contagens["novos"])

        # --- 2. PROCESSOS COM MUDANÇAS ---
        alterados = conn.execute(text("""
            SELECT
                s.*,
                a.fase         AS fase_ant,
                a.nome         AS nome_ant,
                a.substancia   AS subs_ant,
                a.geom         AS geom_ant
            FROM processos_staging s
            JOIN processos_atual a ON a.numero_processo = s.numero_processo
            WHERE
                s.fase IS DISTINCT FROM a.fase
                OR s.nome IS DISTINCT FROM a.nome
                OR NOT ST_Equals(
                    ST_SnapToGrid(s.geom, :snap),
                    ST_SnapToGrid(a.geom, :snap)
                )
        """), {"snap": SNAP_GRID}).mappings().all()

        for row in alterados:
            tipo = _determinar_tipo_mudanca(row)
            _fechar_historico(conn, row["numero_processo"])
            _update_atual(conn, row)
            _insert_historico(conn, row, tipo, execucao_id)
            contagens["atualizados"] += 1

        logger.info("Processos atualizados: %d", contagens["atualizados"])

        # --- 3. PROCESSOS REMOVIDOS ---
        removidos = conn.execute(text("""
            SELECT a.*
            FROM processos_atual a
            LEFT JOIN processos_staging s ON s.numero_processo = a.numero_processo
            WHERE s.id IS NULL
        """)).mappings().all()

        for row in removidos:
            _fechar_historico(conn, row["numero_processo"])
            _insert_historico(conn, row, "REMOVIDO", execucao_id)
            conn.execute(
                text("DELETE FROM processos_atual WHERE numero_processo = :np"),
                {"np": row["numero_processo"]},
            )
            contagens["removidos"] += 1

        logger.info("Processos removidos: %d", contagens["removidos"])

    return contagens


def _determinar_tipo_mudanca(row) -> str:
    """Prioridade: FASE > TITULAR > GEOMETRIA."""
    if row.get("fase") != row.get("fase_ant"):
        return "FASE"
    if row.get("nome") != row.get("nome_ant"):
        return "TITULAR"
    return "GEOMETRIA"


def _insert_atual(conn, row) -> None:
    conn.execute(text("""
        INSERT INTO processos_atual (
            numero_processo, nome, fase, ult_evento, ult_eve_data,
            area_ha, substancia, uso_solo, tipo_requerimento,
            municipio, uf, geom
        ) VALUES (
            :numero_processo, :nome, :fase, :ult_evento, :ult_eve_data,
            :area_ha, :substancia, :uso_solo,
            :tipo_requerimento, :municipio, :uf,
            :geom
        )
        ON CONFLICT (numero_processo) DO NOTHING
    """), dict(row))


def _update_atual(conn, row) -> None:
    conn.execute(text("""
        UPDATE processos_atual SET
            nome              = :nome,
            fase              = :fase,
            ult_evento        = :ult_evento,
            ult_eve_data      = :ult_eve_data,
            area_ha           = :area_ha,
            substancia        = :substancia,
            uso_solo          = :uso_solo,
            tipo_requerimento = :tipo_requerimento,
            municipio         = :municipio,
            geom              = :geom,
            atualizado_em     = NOW()
        WHERE numero_processo = :numero_processo
    """), dict(row))


def _insert_historico(conn, row, tipo_mudanca: str, execucao_id: int) -> None:
    conn.execute(text("""
        INSERT INTO processos_historico (
            numero_processo, nome, fase, ult_evento, ult_eve_data,
            area_ha, substancia, uso_solo, tipo_requerimento,
            municipio, uf, geom,
            tipo_mudanca, valido_de, etl_execucao_id
        ) VALUES (
            :numero_processo, :nome, :fase, :ult_evento, :ult_eve_data,
            :area_ha, :substancia, :uso_solo,
            :tipo_requerimento, :municipio, :uf,
            :geom,
            :tipo_mudanca, COALESCE(CAST(:ult_eve_data AS TIMESTAMP), NOW()), :etl_execucao_id
        )
    """), {
        **dict(row),
        "tipo_mudanca": tipo_mudanca,
        "etl_execucao_id": execucao_id,
    })


def _fechar_historico(conn, numero_processo: str) -> None:
    """Fecha registros históricos abertos (valido_ate IS NULL) para o processo."""
    conn.execute(text("""
        UPDATE processos_historico
        SET valido_ate = NOW()
        WHERE numero_processo = :np
          AND valido_ate IS NULL
    """), {"np": numero_processo})
