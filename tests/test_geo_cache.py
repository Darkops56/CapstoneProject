"""Tests unitarios para el generador y consumidor de Geo-Caché del Actor."""

from pathlib import Path
import pytest
from scripts import prepare_geo_cache


def test_build_geo_cache_creates_artifacts():
    """Verifica que build_geo_cache genere los archivos de referencia en actors/inference/reference_geo/."""
    if (prepare_geo_cache.CURADOS_DIR / "medicion_ruido_curado.csv").exists():
        prepare_geo_cache.build_geo_cache()

    ref_dir = Path("actors/inference/reference_geo")
    assert (ref_dir / "medicion_ruido.parquet").exists(), "Falta medicion_ruido.parquet"
    assert (ref_dir / "delitos_tree.joblib").exists(), "Falta delitos_tree.joblib"
    assert (ref_dir / "contexto_urbano.parquet").exists(), "Falta contexto_urbano.parquet"
