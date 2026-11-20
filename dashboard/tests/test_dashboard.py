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
# Google Drive Exclusive Ingestion Tests (Zero Local Fallback)
# -------------------------------------------------------------------------

def test_data_loader_rejects_unconfigured_drive():
    """Verify that when Google Drive is unconfigured, zero local files are read and error is returned."""
    with patch.dict("os.environ", {}, clear=True):
        df, meta = loader.load_dataset()
        assert df.empty
        assert meta["reason"] == "ERR_GDRIVE_NOT_CONFIGURED"
        assert meta["source"] == "GDRIVE_UNCONFIGURED"


def test_data_loader_drive_error_fails_fast_without_fallback():
    """Verify that network/fetch errors fail fast and return ERR_GDRIVE_FETCH_FAILED without local fallback."""
    with patch.dict("os.environ", {"GDRIVE_CSV_URL": "https://drive.google.com/test.csv"}):
        with patch("src.data_loader.get_latest_gdrive_csv", side_effect=Exception("Connection Timeout")):
            df, meta = loader.load_dataset()
            assert df.empty
            assert meta["reason"] == "ERR_GDRIVE_FETCH_FAILED"
            assert meta["source"] == "GDRIVE_ERROR"


def test_data_loader_successful_gdrive_fetch():
    """Verify successful parsing when Google Drive returns CSV payload."""
    mock_df = pd.DataFrame({
        "listing_id": ["301"],
        "latitud": [-34.60],
        "longitud": [-58.40],
        "costo_total_ars": [950000.0],
    })
    with patch.dict("os.environ", {"GDRIVE_CSV_URL": "https://drive.google.com/test.csv"}):
        with patch("src.data_loader.get_latest_gdrive_csv", return_value=(mock_df, {"source": "GDRIVE_DIRECT_URL", "reason": "SOURCE_GDRIVE_LATEST", "file_name": "alquileres_2026_11.csv"})):
            df, meta = loader.load_dataset()
            assert not df.empty
            assert len(df) == 1
            assert meta["source"] == "GDRIVE_DIRECT_URL"
            assert meta["file_name"] == "alquileres_2026_11.csv"


def test_data_loader_extract_drive_id():
    """Verify folder and file URLs are normalized to raw Google Drive IDs."""
    assert loader._extract_drive_id("10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo") == "10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"
    assert (
        loader._extract_drive_id("https://drive.google.com/drive/u/1/folders/10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo")
        == "10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"
    )
    assert (
        loader._extract_drive_id("https://drive.google.com/file/d/1Ry7pB969p9rtzhdmREu8HmpwbSzSUDka/view?usp=drivesdk")
        == "1Ry7pB969p9rtzhdmREu8HmpwbSzSUDka"
    )


def test_data_loader_folder_api_key_autodetects_latest_csv():
    """Verify folder_id + api_key lists files, selects latest YYYY_MM CSV, and parses UTF-8 payload."""
    list_resp = MagicMock()
    list_resp.raise_for_status.return_value = None
    list_resp.json.return_value = {
        "files": [
            {"id": "old_id", "name": "alquileres_caba_enriquecido_2026_10.csv", "modifiedTime": "2026-10-20T10:00:00Z"},
            {"id": "new_id", "name": "alquileres_caba_enriquecido_2026_11.csv", "modifiedTime": "2026-11-19T18:00:00Z"},
        ]
    }
    file_resp = MagicMock()
    file_resp.raise_for_status.return_value = None
    file_resp.content = "listing_id,barrio,costo_total_ars\n1,Núñez,2203000\n".encode("utf-8")

    with patch("src.data_loader.requests.get", side_effect=[list_resp, file_resp]) as mock_get:
        df, meta = loader.get_latest_gdrive_csv(
            folder_id="https://drive.google.com/drive/u/1/folders/10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo",
            api_key="test-api-key",
        )
        assert len(df) == 1
        assert df.iloc[0]["barrio"] == "Núñez"
        assert meta["source"] == "GDRIVE_FOLDER_API_KEY"
        assert meta["file_name"] == "alquileres_caba_enriquecido_2026_11.csv"
        assert meta["file_id"] == "new_id"
        assert mock_get.call_count == 2
        assert "10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo" in mock_get.call_args_list[0].kwargs["params"]["q"]
        assert mock_get.call_args_list[1].args[0].endswith("/files/new_id")


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


# -------------------------------------------------------------------------
# Crime Heatmap Layer & Graceful Degradation Tests (Negative-Path First)
# -------------------------------------------------------------------------

def _make_base_df(n: int = 40) -> pd.DataFrame:
    np.random.seed(7)
    return pd.DataFrame({
        "listing_id": [str(i) for i in range(n)],
        "latitud": np.linspace(-34.65, -34.55, n),
        "longitud": np.linspace(-58.48, -58.38, n),
        "costo_total_ars": np.linspace(500000.0, 1500000.0, n),
        "precio_justo_ars": np.linspace(550000.0, 1400000.0, n),
        "pct_sobreprecio": np.linspace(-10.0, 15.0, n),
    })


def test_crime_heatmap_full_available_and_p95_winsorization():
    """When both volume and gravity columns exist, weights are in [0, 1] and top 5% saturate at 1.0."""
    df = _make_base_df(100)
    df["densidad_delitos_500m"] = np.concatenate([np.linspace(10.0, 900.0, 94), np.linspace(2000.0, 5000.0, 6)])
    df["indice_gravedad_delitos_500m"] = np.concatenate([np.linspace(20.0, 1800.0, 94), np.linspace(4000.0, 9000.0, 6)])

    clean_df, meta = norm.normalize_schema(df)
    assert meta["crime_heatmap_status"] == "INFO_CRIME_FULL_AVAILABLE"
    assert meta["available_crime_metrics"] == ["VOLUMEN", "GRAVEDAD"]
    for col in ("crime_weight_vol", "crime_weight_grav"):
        assert col in clean_df.columns
        assert np.isfinite(clean_df[col]).all()
        assert (clean_df[col] >= 0.0).all() and (clean_df[col] <= 1.0).all()
        assert (clean_df[col] == 1.0).mean() >= 0.05


def test_crime_heatmap_historical_csv_gravity_unavailable():
    """Historical Drive CSV without indice_gravedad_delitos_500m degrades to INFO_CRIME_GRAVITY_UNAVAILABLE."""
    df = _make_base_df(20)
    df["densidad_delitos_500m"] = np.linspace(100.0, 1000.0, 20)

    clean_df, meta = norm.normalize_schema(df)
    assert meta["crime_heatmap_status"] == "INFO_CRIME_GRAVITY_UNAVAILABLE"
    assert meta["available_crime_metrics"] == ["VOLUMEN"]
    assert "crime_weight_vol" in clean_df.columns
    assert (clean_df["crime_weight_vol"] >= 0.0).all() and (clean_df["crime_weight_vol"] <= 1.0).all()


def test_crime_heatmap_both_columns_missing():
    """CSV without any crime columns emits INFO_CRIME_HEATMAP_UNAVAILABLE without crashing."""
    df = _make_base_df(10)
    clean_df, meta = norm.normalize_schema(df)
    assert meta["crime_heatmap_status"] == "INFO_CRIME_HEATMAP_UNAVAILABLE"
    assert meta["available_crime_metrics"] == []
    assert meta["status"] == "SCHEMA_VALID"


def test_crime_heatmap_zero_nan_and_negative_division_guard():
    """All zeros, NaNs, or negative/dirty strings must produce 0.0 weights without ZeroDivisionError."""
    df = _make_base_df(10)
    df["densidad_delitos_500m"] = [0.0, np.nan, -50.0, "N/A", 0.0, np.nan, 0.0, 0.0, -1.0, 0.0]

    clean_df, meta = norm.normalize_schema(df)
    assert meta["status"] == "SCHEMA_VALID"
    assert np.isfinite(clean_df["crime_weight_vol"]).all()
    assert (clean_df["crime_weight_vol"] == 0.0).all()


def test_crime_heatmap_pydeck_layers_slim_payload_and_fallback():
    """Verify OFF=1 layer, ON=2 layers [HeatmapLayer, ScatterplotLayer], 3-col slim payload <= 250KB, and fallback."""
    clean_raw = _make_base_df(964)
    clean_raw["densidad_delitos_500m"] = np.linspace(50.0, 2500.0, 964)
    clean_raw["indice_gravedad_delitos_500m"] = np.linspace(100.0, 6000.0, 964)
    # Add extra columns to ensure slim projection does NOT serialize them
    for extra_i in range(25):
        clean_raw[f"extra_col_{extra_i}"] = "long_metadata_payload_value_for_test"

    clean_df, _ = norm.normalize_schema(clean_raw)
    df_filtered = clean_df.head(10).copy()

    # 1. Default OFF: 1 layer (ScatterplotLayer)
    deck_off = map_view.build_pydeck_chart(df=df_filtered, show_crime_heatmap=False)
    assert len(deck_off.layers) == 1
    assert deck_off.layers[0].type == "ScatterplotLayer"

    # 2. ON with VOLUMEN and heatmap_df=clean_df
    deck_on = map_view.build_pydeck_chart(
        df=df_filtered,
        show_crime_heatmap=True,
        crime_metric="VOLUMEN",
        heatmap_df=clean_df,
    )
    assert len(deck_on.layers) == 2
    hm_layer, sc_layer = deck_on.layers[0], deck_on.layers[1]
    assert hm_layer.type == "HeatmapLayer"
    assert hm_layer.pickable is False
    assert isinstance(hm_layer.data, list)
    assert len(hm_layer.data) == 964
    assert set(hm_layer.data[0].keys()) == {"longitud", "latitud", "weight"}
    assert hm_layer.color_range[-1][0] >= 160

    assert sc_layer.type == "ScatterplotLayer"
    assert sc_layer.id == "ScatterplotLayer"
    assert sc_layer.pickable is True
    assert sc_layer.stroked is True

    # Slim JSON payload check for HeatmapLayer alone <= 250 KB
    hm_json_kb = len(map_view.pdk.Deck(layers=[hm_layer]).to_json()) / 1024.0
    assert hm_json_kb <= 250.0, f"HeatmapLayer JSON payload {hm_json_kb:.1f} KB exceeded 250 KB"

    # 3. Fallback when GRAVEDAD requested on historical CSV without crime_weight_grav
    hist_df = clean_df.drop(columns=["crime_weight_grav", "indice_gravedad_delitos_500m"])
    deck_fallback = map_view.build_pydeck_chart(
        df=df_filtered,
        show_crime_heatmap=True,
        crime_metric="GRAVEDAD",
        heatmap_df=hist_df,
    )
    assert len(deck_fallback.layers) == 2
    assert deck_fallback.layers[0].type == "HeatmapLayer"

