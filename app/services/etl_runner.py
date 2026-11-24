"""
Service — ETL Runner
Orquestrador do pipeline ETL completo:
  1. Download do shapefile ANM (Pará)
  2. Limpeza e carga na staging
  3. Detecção de mudanças e atualização SCD Tipo 2
  4. Auditoria na tabela etl_execucoes

Suporte ao modo --backfill-demo: injeta dados históricos sintéticos
para demonstração sem histórico real acumulado.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

from app.extensions import db
from app.services.anm_downloader import download_and_extract
from app.services.spatial_cleaner import load_staging
from app.services.change_detector import detect_and_apply_changes

logger = logging.getLogger(__name__)


def _create_execucao(conn) -> int:
    """Cria um registro de execução ETL e retorna seu ID."""
    result = conn.execute(text("""
        INSERT INTO etl_execucoes (status)
        VALUES ('RUNNING')
        RETURNING id
    """))
    execucao_id = result.scalar()
    return execucao_id


def _finish_execucao(conn, execucao_id: int, contagens: dict, mensagem: str, erro: str | None = None) -> None:
    status = "SUCCESS" if erro is None else "ERROR"
    conn.execute(
        text("""
            UPDATE etl_execucoes
            SET finalizado_em = NOW(),
                status        = :status,
                novos         = :novos,
                atualizados   = :atualizados,
                removidos     = :removidos,
                total_staging = :total_staging,
                mensagem      = :mensagem,
                erro          = :erro
            WHERE id = :execucao_id
        """),
        {
            "status": status,
            "novos": contagens.get("novos", 0),
            "atualizados": contagens.get("atualizados", 0),
            "removidos": contagens.get("removidos", 0),
            "total_staging": contagens.get("total_staging", 0),
            "mensagem": mensagem,
            "erro": erro,
            "execucao_id": execucao_id,
        },
    )


def run_pipeline(force_download: bool = False) -> dict:
    """
    Executa o pipeline ETL completo.

    Returns:
        Dict com resultado: {execucao_id, status, novos, atualizados, removidos}
    """
    logger.info("=" * 60)
    logger.info("Iniciando pipeline ETL — SIGMINE PA")
    logger.info("=" * 60)

    contagens: dict = {"novos": 0, "atualizados": 0, "removidos": 0, "total_staging": 0}
    execucao_id: int | None = None

    try:
        # Cria registro de auditoria
        with db.engine.begin() as conn:
            execucao_id = _create_execucao(conn)
        logger.info("Execução ETL #%d iniciada", execucao_id)

        # 1. Download
        shp_path = download_and_extract(force_download=force_download)
        logger.info("Shapefile: %s", shp_path)

        # 2. Staging
        total = load_staging(shp_path, execucao_id)
        contagens["total_staging"] = total

        # 3. Detecção de mudanças
        mudancas = detect_and_apply_changes(execucao_id)
        contagens.update(mudancas)

        mensagem = (
            f"ETL concluído: {total} no staging | "
            f"{contagens['novos']} novos | "
            f"{contagens['atualizados']} atualizados | "
            f"{contagens['removidos']} removidos"
        )
        logger.info(mensagem)

        with db.engine.begin() as conn:
            _finish_execucao(conn, execucao_id, contagens, mensagem)

        return {"execucao_id": execucao_id, "status": "SUCCESS", **contagens}

    except Exception as exc:
        logger.exception("Erro no pipeline ETL: %s", exc)
        if execucao_id:
            with db.engine.begin() as conn:
                _finish_execucao(conn, execucao_id, contagens, "Erro", str(exc))
        raise


def run_backfill_demo(app) -> None:
    """
    Modo de demonstração: injeta snapshots históricos sintéticos
    com datas retroativas para simular meses de coleta.
    Útil para apresentações sem histórico real acumulado.
    """
    logger.info("Iniciando backfill demo…")
    with app.app_context():
        with db.engine.begin() as conn:
            # Verifica se já existe histórico
            count = conn.execute(text("SELECT COUNT(*) FROM processos_historico")).scalar()
            if count > 0:
                logger.info("Histórico já existe (%d registros). Skipping backfill.", count)
                return

            # Busca processos atuais como base
            processos = conn.execute(text("""
                SELECT numero_processo, nome, fase, ult_evento, area_ha,
                       substancia, municipio, geom
                FROM processos_atual
                LIMIT 200
            """)).mappings().all()

            if not processos:
                logger.warning("Nenhum processo em processos_atual. Execute o ETL primeiro.")
                return

            now = datetime.now(tz=timezone.utc)
            # Cria 6 snapshots mensais retroativos
            fases_ciclo = [
                "Requerimento de Pesquisa",
                "Autorização de Pesquisa",
                "Requerimento de Lavra",
                "Concessão de Lavra",
            ]

            exec_id_demo = conn.execute(text("""
                INSERT INTO etl_execucoes (status, mensagem)
                VALUES ('SUCCESS', 'Backfill demo')
                RETURNING id
            """)).scalar()

            inserted = 0
            for i, proc in enumerate(processos):
                # Registra como NOVO 6 meses atrás
                data_novo = now - timedelta(days=180)
                conn.execute(text("""
                    INSERT INTO processos_historico (
                        numero_processo, nome, fase, area_ha, substancia,
                        municipio, geom, tipo_mudanca, valido_de,
                        valido_ate, etl_execucao_id
                    ) VALUES (
                        :np, :nome, :fase, :area_ha, :substancia,
                        :municipio, :geom, 'NOVO', :valido_de,
                        :valido_ate, :exec_id
                    )
                """), {
                    "np": proc["numero_processo"],
                    "nome": proc["nome"],
                    "fase": fases_ciclo[0],
                    "area_ha": proc["area_ha"],
                    "substancia": proc["substancia"],
                    "municipio": proc["municipio"],
                    "geom": proc["geom"],
                    "valido_de": data_novo,
                    "valido_ate": now - timedelta(days=90) if i % 3 == 0 else None,
                    "exec_id": exec_id_demo,
                })
                inserted += 1

                # Para alguns, adiciona mudança de fase
                if i % 3 == 0:
                    conn.execute(text("""
                        INSERT INTO processos_historico (
                            numero_processo, nome, fase, area_ha, substancia,
                            municipio, geom, tipo_mudanca, valido_de,
                            etl_execucao_id
                        ) VALUES (
                            :np, :nome, :fase, :area_ha, :substancia,
                            :municipio, :geom, 'FASE', :valido_de, :exec_id
                        )
                    """), {
                        "np": proc["numero_processo"],
                        "nome": proc["nome"],
                        "fase": fases_ciclo[min(1, len(fases_ciclo) - 1)],
                        "area_ha": proc["area_ha"],
                        "substancia": proc["substancia"],
                        "municipio": proc["municipio"],
                        "geom": proc["geom"],
                        "valido_de": now - timedelta(days=90),
                        "exec_id": exec_id_demo,
                    })
                    inserted += 1

            logger.info("Backfill demo: %d registros históricos inseridos", inserted)
