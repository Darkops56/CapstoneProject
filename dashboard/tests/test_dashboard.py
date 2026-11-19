"""Deterministic test suite for the Interactive Property Map Dashboard.
Negative-path first, boundary verification, and performance benchmarks.
"""
import time
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

import src.config as cfg
import src.normalizer as norm
import src.data_loader as loader
import src.map_view as map_view


# -------------------------------------------------------------------------
# Price Semaphore & Boundary Tests
# -------------------------------------------------------------------------

def test_classify_price_status_boundaries():
    """Verify standard thresholds: <= -5% is Bajo Precio, -5%..+10% is Precio Justo, > 10% is Sobreprecio."""
    # Boundary: -5.0% -> Bajo Precio
    status, label, color = norm.classify_price_status(-5.0)
    assert status == "BAJO_PRECIO"
    assert "Bajo Precio" in label
    assert color == cfg.COLOR_BAJO_PRECIO

    # Just above -5.0% -> Precio Justo
    status, label, color = norm.classify_price_status(-4.99)
    assert status == "PRECIO_JUSTO"
    assert "Precio Justo" in label
    assert color == cfg.COLOR_PRECIO_JUSTO

    # Boundary: +10.0% -> Precio Justo
    status, label, color = norm.classify_price_status(10.0)
    assert status == "PRECIO_JUSTO"
    assert "Precio Justo" in label
    assert color == cfg.COLOR_PRECIO_JUSTO

    # Boundary: +10.01% -> Sobreprecio
    status, label, color = norm.classify_price_status(10.01)
    assert status == "SOBREPRECIO"
    assert "Sobreprecio" in label
    assert color == cfg.COLOR_SOBREPRECIO


# -------------------------------------------------------------------------
# Normalizer Tests (Reconciliation, Boundaries, Drop & Degradation)
# -------------------------------------------------------------------------

def test_normalizer_missing_required_columns():
    """Verify rejection with ERR_SCHEMA_MISSING_REQUIRED_COLUMNS when critical columns are absent."""
    broken_df = pd.DataFrame({"listing_id": [1, 2], "barrio": ["Palermo", "Belgrano"]})
    clean_df, meta = norm.normalize_schema(broken_df)
    assert clean_df.empty
    assert meta["status"] == "SCHEMA_INVALID"
    assert meta["reason"] == "ERR_SCHEMA_MISSING_REQUIRED_COLUMNS"
    assert "costo_total_ars" in meta["missing_columns"]


def test_normalizer_caba_bbox_drop():
    """Verify out-of-bounds coordinates (or NaN / 0,0) are filtered out and tagged with AUDIT_OUT_OF_BOUNDS_DROPPED."""
    raw_df = pd.DataFrame({
        "listing_id": ["1", "2", "3", "4"],
        "latitud": [-34.60, np.nan, -34.00, -34.58],  # row 3 is outside CABA, row 2 is NaN
        "longitud": [-58.40, -58.42, -58.40, -58.41],
        "costo_total_ars": [800000.0, 900000.0, 750000.0, 600000.0],
        "precio_justo_ars": [850000.0, 900000.0, 800000.0, 600000.0],
        "pct_sobreprecio": [-5.88, 0.0, -6.25, 0.0],
    })
    clean_df, meta = norm.normalize_schema(raw_df)
    assert len(clean_df) == 2
    assert set(clean_df["listing_id"]) == {"1", "4"}
    assert meta["dropped_out_of_bounds"] == 2
    assert meta["audit_tag"] == "AUDIT_OUT_OF_BOUNDS_DROPPED"


def test_normalizer_drive_schema_aliases():
    """Verify reconciliation of Google Drive schema columns to canonical format."""
    drive_df = pd.DataFrame({
        "listing_id": ["101"],
        "latitud": [-34.59],
        "longitud": [-58.42],
        "costo_total_ars": [1000000.0],
        "precio_justo_ars": [900000.0],
        "desvio_precio_pct": [11.11],
        "cluster_habitabilidad": [2],
        "score_soltero": [68.5],
        "calificacion_familia": ["RECOMENDADA"],
        "calificacion_soltero": ["ALTAMENTE RECOMENDADA"],
    })
    clean_df, meta = norm.normalize_schema(drive_df)
    assert len(clean_df) == 1
    assert "pct_sobreprecio" in clean_df.columns
    assert clean_df.loc[0, "pct_sobreprecio"] == pytest.approx(11.11, 0.01)
    assert clean_df.loc[0, "cluster_id"] == 2
    assert clean_df.loc[0, "score_soltero_ejecutivo"] == pytest.approx(68.5, 0.01)
    assert clean_df.loc[0, "recomendacion_familia"] == "RECOMENDADA"
    assert clean_df.loc[0, "recomendacion_soltero_ejecutivo"] == "ALTAMENTE RECOMENDADA"


def test_normalizer_amenities_graceful_degradation():
    """Verify detection of granular amenities and graceful degradation when absent."""
    # Case A: Granular amenities present
    full_df = pd.DataFrame({
        "listing_id": ["201"],
        "latitud": [-34.60],
        "longitud": [-58.40],
        "costo_total_ars": [700000.0],
        "precio_justo_ars": [750000.0],
        "has_parrilla": [1],
        "has_pileta": [0],
        "has_gimnasio": [1],
    })
    _, meta_full = norm.normalize_schema(full_df)
    assert meta_full["amenities_status"] == "INFO_FULL_AMENITIES_AVAILABLE"
    assert "has_parrilla" in meta_full["available_amenities"]

    # Case B: Granular amenities absent
    reduced_df = pd.DataFrame({
        "listing_id": ["202"],
        "latitud": [-34.60],
        "longitud": [-58.40],
        "costo_total_ars": [700000.0],
        "precio_justo_ars": [750000.0],
        "apto_mascotas": [1],
        "cocheras": [1],
    })
    _, meta_reduced = norm.normalize_schema(reduced_df)
    assert meta_reduced["amenities_status"] == "INFO_GRANULAR_AMENITIES_UNAVAILABLE"
    assert "has_parrilla" not in meta_reduced["available_amenities"]


# -------------------------------------------------------------------------
# Data Loader & Fallback Tests
# -------------------------------------------------------------------------

def test_data_loader_fallback_when_unconfigured():
    """Verify transparent fallback to local data when Google Drive is unconfigured."""
    df, meta = loader.load_dataset(local_fallback_path="data/fallback_data.csv")
    assert not df.empty
    assert len(df) == 964
    assert meta["reason"] == "WARN_DRIVE_FALLBACK_ACTIVE"
    assert meta["source"] == "LOCAL_FALLBACK"


def test_data_loader_fallback_on_drive_error():
    """Verify graceful catch of network / timeout errors and fallback to local seed data."""
    with patch("src.data_loader.get_latest_gdrive_csv", side_effect=Exception("Connection Timeout")):
        df, meta = loader.load_dataset(local_fallback_path="data/fallback_data.csv")
        assert not df.empty
        assert len(df) == 964
        assert meta["reason"] == "WARN_DRIVE_FALLBACK_ACTIVE"


# -------------------------------------------------------------------------
# Map View Tests
# -------------------------------------------------------------------------

def test_map_view_deck_structure():
    """Verify PyDeck Deck object builds cleanly with Carto Positron basemap."""
    sample_df = pd.DataFrame({
        "listing_id": ["1", "2"],
        "latitud": [-34.58, -34.60],
        "longitud": [-58.42, -58.40],
        "costo_total_ars": [800000.0, 1200000.0],
        "precio_justo_ars": [850000.0, 1100000.0],
        "pct_sobreprecio": [-5.88, 9.09],
        "score_familia": [82.0, 65.0],
        "score_soltero_ejecutivo": [75.0, 80.0],
        "recomendacion_familia": ["ALTAMENTE RECOMENDADA", "RECOMENDADA"],
        "recomendacion_soltero_ejecutivo": ["RECOMENDADA", "ALTAMENTE RECOMENDADA"],
        "barrio": ["Palermo", "Recoleta"],
        "ambientes": [3, 2],
        "cocheras": [1, 0],
        "apto_mascotas": [1, 0],
    })
    clean_df, _ = norm.normalize_schema(sample_df)
    deck = map_view.build_pydeck_chart(clean_df, profile="FAMILIA", color_mode="PRECIO")
    assert deck is not None
    assert deck.map_style == cfg.CARTO_POSITRON_STYLE
    assert len(deck.layers) >= 1
    assert deck.layers[0].type == "ScatterplotLayer"


def test_map_view_formatted_tooltips():
    """Verify tooltips reference pre-formatted strings rather than Python format specifiers."""
    sample_df = pd.DataFrame({
        "listing_id": ["999"],
        "latitud": [-34.58],
        "longitud": [-58.42],
        "costo_total_ars": [1250000.0],
        "precio_justo_ars": [1100000.0],
        "pct_sobreprecio": [13.63],
        "score_familia": [77.5],
        "score_soltero_ejecutivo": [82.0],
        "recomendacion_familia": ["RECOMENDADA"],
        "recomendacion_soltero_ejecutivo": ["ALTAMENTE RECOMENDADA"],
        "barrio": ["Palermo"],
        "ambientes": [3],
        "cocheras": [1],
        "apto_mascotas": [1],
    })
    clean_df, _ = norm.normalize_schema(sample_df)
    deck = map_view.build_pydeck_chart(clean_df, profile="FAMILIA", color_mode="PRECIO")
    tooltip_html = (deck._tooltip or {}).get("html", "")
    assert "{costo_total_fmt}" in tooltip_html
    assert "{precio_justo_fmt}" in tooltip_html
    assert "{desvio_fmt}" in tooltip_html
    assert "{costo_total_ars:,.0f}" not in tooltip_html


# -------------------------------------------------------------------------
# UI Components & Filter Helper Tests
# -------------------------------------------------------------------------

def test_ui_components_filter_logic():
    """Verify filtering logic correctly extracts subsets across multi-feature criteria."""
    import src.ui_components as ui
    sample_df = pd.DataFrame({
        "listing_id": ["1", "2", "3"],
        "latitud": [-34.58, -34.60, -34.62],
        "longitud": [-58.42, -58.40, -58.38],
        "costo_total_ars": [500000.0, 900000.0, 1500000.0],
        "precio_justo_ars": [600000.0, 850000.0, 1400000.0],
        "pct_sobreprecio": [-16.6, 5.8, 7.1],
        "score_familia": [85.0, 60.0, 70.0],
        "score_soltero_ejecutivo": [75.0, 80.0, 65.0],
        "recomendacion_familia": ["ALTAMENTE RECOMENDADA", "RECOMENDADA", "RECOMENDADA"],
        "recomendacion_soltero_ejecutivo": ["RECOMENDADA", "ALTAMENTE RECOMENDADA", "RECOMENDADA"],
        "barrio": ["Palermo", "Belgrano", "Caballito"],
        "ambientes": [2, 3, 4],
        "cocheras": [1, 0, 1],
        "apto_mascotas": [1, 0, 1],
        "has_parrilla": [1, 0, 0],
    })
    clean_df, meta = norm.normalize_schema(sample_df)

    # Test filtering with helper
    filters = {
        "max_price": 1000000.0,
        "selected_barrios": ["Palermo", "Belgrano"],
        "min_ambientes": 2,
        "apto_mascotas": True,
        "con_cochera": True,
        "has_parrilla": True,
        "selected_price_statuses": ["BAJO_PRECIO"],
    }
    filtered_df = ui.apply_filters(clean_df, filters)
    assert len(filtered_df) == 1
    assert filtered_df.iloc[0]["listing_id"] == "1"


# -------------------------------------------------------------------------
# Performance & Scalability Test (10,000 synthetic rows)
# -------------------------------------------------------------------------

def test_filter_performance():
    """Benchmark: vector filtering over 10,000 properties MUST complete in < 50ms."""
    n_rows = 10000
    np.random.seed(42)
    synthetic_df = pd.DataFrame({
        "listing_id": [str(i) for i in range(n_rows)],
        "latitud": np.random.uniform(cfg.CABA_BBOX["lat_min"], cfg.CABA_BBOX["lat_max"], n_rows),
        "longitud": np.random.uniform(cfg.CABA_BBOX["lon_min"], cfg.CABA_BBOX["lon_max"], n_rows),
        "costo_total_ars": np.random.uniform(300000.0, 2000000.0, n_rows),
        "precio_justo_ars": np.random.uniform(300000.0, 2000000.0, n_rows),
        "pct_sobreprecio": np.random.uniform(-25.0, 25.0, n_rows),
        "score_familia": np.random.uniform(10.0, 95.0, n_rows),
        "score_soltero_ejecutivo": np.random.uniform(10.0, 95.0, n_rows),
        "apto_mascotas": np.random.choice([0, 1], n_rows),
        "cocheras": np.random.choice([0, 1, 2], n_rows),
        "ambientes": np.random.choice([1, 2, 3, 4], n_rows),
        "barrio": np.random.choice(["Palermo", "Belgrano", "Caballito", "Flores", "Balvanera"], n_rows),
        "has_parrilla": np.random.choice([0, 1], n_rows),
        "has_pileta": np.random.choice([0, 1], n_rows),
    })
    clean_df, _ = norm.normalize_schema(synthetic_df)

    t0 = time.perf_counter()
    # Complex multi-feature combined filter
    mask = (
        (clean_df["costo_total_ars"] <= 1200000.0) &
        (clean_df["ambientes"] >= 2) &
        (clean_df["apto_mascotas"] == 1) &
        (clean_df["cocheras"] >= 1) &
        (clean_df["pct_sobreprecio"] <= cfg.PRICE_CUT_HIGH_PCT) &
        (clean_df["barrio"].isin(["Palermo", "Belgrano", "Caballito"]))
    )
    filtered = clean_df[mask]
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert len(filtered) > 0
    assert elapsed_ms < 50.0, f"Filter took {elapsed_ms:.2f}ms, exceeding 50ms requirement"
