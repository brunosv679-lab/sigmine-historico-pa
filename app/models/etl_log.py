"""
Model — EtlLog
Acesso à tabela de auditoria das execuções ETL.
"""
from __future__ import annotations

from sqlalchemy import text
from app.extensions import db


def get_ultimas_execucoes(limit: int = 10) -> list[dict]:
    """Retorna as últimas execuções ETL para monitoramento."""
    sql = text("""
        SELECT
            id,
            iniciado_em::text,
            finalizado_em::text,
            status,
            novos,
            atualizados,
            removidos,
            total_staging,
            mensagem
        FROM etl_execucoes
        ORDER BY iniciado_em DESC
        LIMIT :lim
    """).bindparams(text("lim").bindparams(lim=limit))

    with db.engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, iniciado_em::text, finalizado_em::text,
                       status, novos, atualizados, removidos,
                       total_staging, mensagem
                FROM etl_execucoes
                ORDER BY iniciado_em DESC
                LIMIT :lim
            """),
            {"lim": limit},
        ).mappings().all()
    return [dict(r) for r in rows]


def get_ultima_execucao_bem_sucedida() -> dict | None:
    """Retorna a última execução bem-sucedida."""
    with db.engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, iniciado_em::text, finalizado_em::text,
                       novos, atualizados, removidos, total_staging
                FROM etl_execucoes
                WHERE status = 'SUCCESS'
                ORDER BY iniciado_em DESC
                LIMIT 1
            """)
        ).mappings().first()
    return dict(row) if row else None
