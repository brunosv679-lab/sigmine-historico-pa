"""
Controller — Web Controller
Rotas HTML: Mapa principal e Mapa de Dinâmica.
"""
from flask import Blueprint, render_template
from app.models.etl_log import get_ultima_execucao_bem_sucedida
from app.models.processo_atual import get_total_count, get_fases_disponiveis, get_substancias_disponiveis

web_bp = Blueprint("web", __name__)


@web_bp.route("/")
def index():
    """Mapa principal com painel lateral e linha do tempo de processos."""
    try:
        ultima_etl = get_ultima_execucao_bem_sucedida()
        total = get_total_count()
        fases = get_fases_disponiveis()
        substancias = get_substancias_disponiveis()
    except Exception:
        ultima_etl, total, fases, substancias = None, 0, [], []

    return render_template(
        "index.html",
        ultima_etl=ultima_etl,
        total_processos=total,
        fases=fases,
        substancias=substancias,
    )


@web_bp.route("/dinamica")
def dinamica():
    """Mapas e gráficos de dinâmica temporal dos processos."""
    try:
        ultima_etl = get_ultima_execucao_bem_sucedida()
    except Exception:
        ultima_etl = None

    return render_template("dinamica.html", ultima_etl=ultima_etl)


@web_bp.route("/health")
def health():
    """Endpoint de saúde para monitoramento."""
    from flask import jsonify
    try:
        total = get_total_count()
        return jsonify({"status": "ok", "processos": total}), 200
    except Exception as exc:
        return jsonify({"status": "error", "detail": str(exc)}), 500


@web_bp.route("/sobre")
def sobre():
    return render_template("sobre.html")
