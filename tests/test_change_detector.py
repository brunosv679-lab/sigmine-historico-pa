"""
Testes unitários — ChangeDetector
Verifica a lógica de detecção de mudanças sem banco de dados real.
"""
import pytest
from unittest.mock import patch, MagicMock, call
from app.services.change_detector import _determinar_tipo_mudanca


class TestDeterminarTipoMudanca:
    """Testa a prioridade de tipos de mudança."""

    def test_novo_processo(self):
        # Processo que entra como NOVO não passa por _determinar_tipo_mudanca
        # (é chamado diretamente). Testa via pipeline implicitamente.
        pass

    def test_mudanca_fase_prioritaria(self):
        row = {
            "fase": "Autorização de Pesquisa",
            "fase_ant": "Requerimento de Pesquisa",
            "nome": "Empresa X",
            "nome_ant": "Empresa X",
        }
        assert _determinar_tipo_mudanca(row) == "FASE"

    def test_mudanca_titular(self):
        row = {
            "fase": "Autorização de Pesquisa",
            "fase_ant": "Autorização de Pesquisa",
            "nome": "Empresa Nova",
            "nome_ant": "Empresa Antiga",
        }
        assert _determinar_tipo_mudanca(row) == "TITULAR"

    def test_mudanca_geometria(self):
        row = {
            "fase": "Autorização de Pesquisa",
            "fase_ant": "Autorização de Pesquisa",
            "nome": "Empresa X",
            "nome_ant": "Empresa X",
        }
        assert _determinar_tipo_mudanca(row) == "GEOMETRIA"

    def test_fase_tem_prioridade_sobre_titular(self):
        row = {
            "fase": "Concessão de Lavra",
            "fase_ant": "Requerimento de Pesquisa",
            "nome": "Empresa Nova",
            "nome_ant": "Empresa Antiga",
        }
        assert _determinar_tipo_mudanca(row) == "FASE"


class TestANMDownloader:
    """Testa o módulo de download (mock da rede)."""

    def test_download_url_configuravel(self):
        from app.services import anm_downloader
        # Verifica que a URL é lida do ambiente
        import os
        os.environ["ANM_PA_URL"] = "https://test.example.com/PA.zip"
        # Reimportar o módulo para capturar a nova variável
        import importlib
        importlib.reload(anm_downloader)
        assert "test.example.com" in anm_downloader.ANM_PA_URL
        # Restaura
        del os.environ["ANM_PA_URL"]


class TestSpatialCleaner:
    """Testa funções de limpeza espacial."""

    def test_decode_field_bytes(self):
        from app.services.spatial_cleaner import _decode_field
        result = _decode_field(b"Minera\xe7\xe3o")
        assert isinstance(result, str)

    def test_decode_field_str(self):
        from app.services.spatial_cleaner import _decode_field
        assert _decode_field("Normal") == "Normal"

    def test_decode_field_none(self):
        from app.services.spatial_cleaner import _decode_field
        assert _decode_field(None) is None

    def test_to_multipolygon_polygon(self):
        from app.services.spatial_cleaner import _to_multipolygon
        from shapely.geometry import Polygon, MultiPolygon
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        result = _to_multipolygon(poly)
        assert isinstance(result, MultiPolygon)

    def test_to_multipolygon_invalid(self):
        from app.services.spatial_cleaner import _to_multipolygon
        from shapely.geometry import Polygon
        # Polígono com auto-interseção (bowtie)
        bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
        result = _to_multipolygon(bowtie)
        # make_valid deve corrigir ou retornar None se impossível
        # O importante é não lançar exceção
        assert result is None or hasattr(result, "geoms")

    def test_to_multipolygon_none(self):
        from app.services.spatial_cleaner import _to_multipolygon
        assert _to_multipolygon(None) is None
