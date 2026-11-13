"""Suite TDD (Clase 43) para validar ETL, enriquecimiento geoespacial y entregables de Fase 1 y 2."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config import settings as config
from etl import etl_pipeline as etl


# ---------------------------------------------------------------------------
# 1. Tests unitarios de reglas ETL (Rojo -> Verde -> Refactor)
# ---------------------------------------------------------------------------


def test_normalize_caba_coord_shifted_decimal():
    """Divide sucesivamente por 10 hasta ubicar latitud/longitud en CABA."""
    assert etl.normalize_caba_coord(-34584136.0, config.CABA_LAT_MIN, config.CABA_LAT_MAX) == pytest.approx(-34.584136)
    assert etl.normalize_caba_coord(-58454704.0, config.CABA_LON_MIN, config.CABA_LON_MAX) == pytest.approx(-58.454704)
    assert etl.normalize_caba_coord(-3.46123e16, config.CABA_LAT_MIN, config.CABA_LAT_MAX) == pytest.approx(-34.6123)
    assert np.isnan(etl.normalize_caba_coord(None, config.CABA_LAT_MIN, config.CABA_LAT_MAX))
    assert np.isnan(etl.normalize_caba_coord(999999.0, config.CABA_LAT_MIN, config.CABA_LAT_MAX))


def test_parse_price_ars_usd_and_ars():
    """Unifica ARS y USD usando TIPO_CAMBIO_BASE, FACTOR_IMPUESTOS_USD e IMPUESTO_SELLOS_ALQUILER."""
    assert etl.parse_price_ars(1_000_000, "ARS", tipo_cambio=1200.0, factor_usd=1.0, sellos=0.0) == pytest.approx(1_000_000.0)
    assert etl.parse_price_ars(1000, "USD", tipo_cambio=1200.0, factor_usd=1.0, sellos=0.0) == pytest.approx(1_200_000.0)
    assert etl.parse_price_ars(1000, "USD", tipo_cambio=1200.0, factor_usd=1.1, sellos=0.05) == pytest.approx(1_386_000.0)
    assert np.isnan(etl.parse_price_ars(0, "USD"))
    assert np.isnan(etl.parse_price_ars(-500, "ARS"))


def test_extract_expenses_ars_structured_and_regex():
    """Extrae expensas estructuradas, por regex o detecta expensas incluidas sin confundir con alquiler."""
    item_struct = {
        "prices": {"detailPricesArray": [{"price": "Alquiler $ 1.200.000", "expenses": "Expensas $ 382.000"}]},
        "description": "",
    }
    val, src = etl.extract_expenses_ars(item_struct)
    assert val == pytest.approx(382_000.0)
    assert src == "structured"

    item_incl = {
        "prices": {"detailPricesArray": [{"price": "Alquiler $ 2.200.000", "expenses": None}]},
        "description": "VALOR MENSUAL: $2.200.000 – EXPENSAS INCLUIDAS. Excelente depto.",
    }
    val_incl, src_incl = etl.extract_expenses_ars(item_incl)
    assert val_incl == pytest.approx(0.0)
    assert src_incl == "included_in_rent"

    item_regex = {
        "prices": {"detailPricesArray": []},
        "description": "ALQUILER MAS GASTOS - EXPENSAS (oct 26) $ 172.000.- AYSA $ 26.000.",
    }
    val_rx, src_rx = etl.extract_expenses_ars(item_regex)
    assert val_rx == pytest.approx(172_000.0)
    assert src_rx == "regex_desc"

    item_regex_sept = {
        "prices": {"detailPricesArray": []},
        "description": "Expensas: (septiembre/26) $450.000 Para mas información...",
    }
    val_rx2, _ = etl.extract_expenses_ars(item_regex_sept)
    assert val_rx2 == pytest.approx(450_000.0)


def test_extract_apto_mascotas_negation_overrides_tag():
    """Si la descripción niega mascotas explícitamente, debe devolver 0 aunque el tag diga ADMITS_PETS."""
    item_contradiction = {
        "detailExtraTopLevel": {"pills": [{"id": "ADMITS_PETS", "value": "Acepta mascotas"}]},
        "featuresListCardSimplified": [{"featureId": "1000002", "featureLabel": "Permite mascotas"}],
        "description": "Hermoso 2 ambientes. Ajuste trimestral por IPC. No se aceptan mascotas.",
    }
    assert etl.extract_apto_mascotas(item_contradiction) == 0

    item_positive = {
        "detailExtraTopLevel": {"pills": [{"id": "ADMITS_PETS", "value": "Acepta mascotas"}]},
        "featuresListCardSimplified": [],
        "description": "Luminoso departamento con balcón.",
    }
    assert etl.extract_apto_mascotas(item_positive) == 1

    item_desc_only = {
        "detailExtraTopLevel": {},
        "featuresListCardSimplified": [],
        "description": "Departamento en Palermo, apto mascotas pequeñas.",
    }
    assert etl.extract_apto_mascotas(item_desc_only) == 1


def test_extract_amenities_profiles():
    """Diferencia amenities para perfil soltero vs familia y calcula score_amenities numérico."""
    item = {
        "mainFeatures": [{"id": "CFT7", "value": "1 coch."}],
        "featuresListCardSimplified": [
            {"featureId": "1000068", "featureLabel": "Gimnasio"},
            {"featureId": "1000079", "featureLabel": "Pileta"},
            {"featureId": "1000078", "featureLabel": "Parrilla"},
            {"featureId": "1000092", "featureLabel": "SUM"},
            {"featureId": "1000097", "featureLabel": "Vigilancia"},
            {"featureId": "1000100", "featureLabel": "Balcón"},
        ],
        "description": "Edificio con coworking, seguridad 24 hs y solarium.",
    }
    res = etl.extract_amenities(item)
    assert res["has_gimnasio"] == 1
    assert res["has_pileta"] == 1
    assert res["has_parrilla"] == 1
    assert res["has_sum_coworking"] == 1
    assert res["has_seguridad"] == 1
    assert res["has_balcon_terraza"] == 1
    assert res["has_cochera"] == 1
    assert res["score_amenities"] > 0
    assert res["score_amenities_familia"] > 0
    assert res["score_amenities_soltero"] > 0


def test_enrich_with_schools_reprojects_caba_local_crs(tmp_path):
    """Verifica reproyección desde CRS local CABA a EPSG:4326 y filtro de niveles familiares."""
    # Coordenada real de Ayacucho 1670 (Recoleta) en CRS local CABA -> ~ (-34.590, -58.392)
    esc_df = pd.DataFrame(
        {
            "nen_mde": [
                "Nivel primario común",
                "Nivel inicial común - Jardín de infantes",
                "Nivel secundario de jóvenes y adultos",  # debe filtrarse
            ],
            "geometry": [
                "POINT (26519.67 74333.08)",
                "POINT (26519.67 74333.08)",
                "POINT (26519.67 74333.08)",
            ],
        }
    )
    esc_xlsx = tmp_path / "escuelas.xlsx"
    esc_df.to_excel(esc_xlsx, index=False)

    props = pd.DataFrame({"latitud": [-34.5907], "longitud": [-58.3917]})
    enriched, audit = etl.enrich_with_schools(props, escuelas_path=esc_xlsx, radius_m=500.0)
    assert audit["escuelas_familias_filtered"] == 2
    assert enriched.loc[0, "escuelas_familias_500m"] == 2
    assert enriched.loc[0, "distancia_escuela_m"] < 250.0


def test_enrich_with_noise_within_and_nearest_fallback(tmp_path):
    """Verifica sjoin(within) y respaldo sjoin_nearest para puntos en borde/fuera de polígono."""
    ruido_csv = tmp_path / "ruido.csv"
    pd.DataFrame(
        {
            "wkt": ["MULTIPOLYGON (((-58.40 -34.60, -58.39 -34.60, -58.39 -34.59, -58.40 -34.59, -58.40 -34.60)))"],
            "limite_inferior_rango_db": [60.0],
            "limite_superior_rango_db": [65.0],
            "comuna": [2],
            "rango_db": ["60-65"],
        }
    ).to_csv(ruido_csv, index=False)

    props = pd.DataFrame(
        {
            "listing_id": ["inside", "edge"],
            "latitud": [-34.595, -34.589],
            "longitud": [-58.395, -58.395],
            "barrio": ["Recoleta", "Recoleta"],
        }
    )
    enriched, audit = etl.enrich_with_noise(props, ruido_path=ruido_csv)
    assert audit["matched_within"] == 1
    assert audit["imputed_nearest"] == 1
    assert enriched["ruido_db_promedio"].tolist() == [62.5, 62.5]
    assert enriched["ruido_imputado_nearest"].tolist() == [0, 1]


# ---------------------------------------------------------------------------
# 2. Tests de integración sobre entregables de Fase 1 y Fase 2
# ---------------------------------------------------------------------------


def test_producto1_outputs_exist_and_meet_contract():
    """Verifica que producto1_dataset_curado.csv y eda_stats.json cumplan las reglas del proyecto."""
    if not config.OUTPUT_CURATED_CSV.exists() or not config.OUTPUT_EDA_JSON.exists():
        pytest.skip("Los entregables de Fase 1 y 2 aún no fueron generados.")

    df = pd.read_csv(config.OUTPUT_CURATED_CSV)
    assert config.TARGET_COL in df.columns
    features = [c for c in df.columns if c != config.TARGET_COL]
    assert 1 <= len(features) <= 10, f"Se esperaban <= 10 features, encontradas {len(features)}: {features}"
    assert "apto_mascotas" in features
    assert "score_amenities" in features
    assert df.isna().sum().sum() == 0, "El dataset curado final no debe contener valores nulos."
    assert (df[config.TARGET_COL] > 0).all()

    with open(config.OUTPUT_EDA_JSON, "r", encoding="utf-8") as f:
        stats_report = json.load(f)

    assert "audit_etl" in stats_report
    assert "descriptive_stats" in stats_report
    assert "hypothesis_tests" in stats_report
    assert "multicollinearity_vif" in stats_report
    assert "feature_selection" in stats_report
    assert len(stats_report["feature_selection"]["selected_features"]) <= 10
    for feat, vif_val in stats_report["feature_selection"]["final_vif"].items():
        assert vif_val < 10.0, f"VIF demasiado alto en feature final {feat}: {vif_val}"


def test_datasets_curados_folder_has_5_valid_csvs():
    """Verifica que DatasetsCurados contenga los 5 archivos curados en formato .csv y coordenadas WGS84 CABA."""
    expected = [
        "zonaprop_alquileres_curado.csv",
        "medicion_ruido_curado.csv",
        "delitos_2022_curado.csv",
        "establecimientos_educativos_curado.csv",
        "bocas_de_subte_curado.csv",
    ]
    for fname in expected:
        fpath = config.DATASETS_CURADOS_DIR / fname
        assert fpath.exists(), f"Falta {fpath}"
        df = pd.read_csv(fpath, nrows=50)
        assert len(df) > 0
        if "latitud" in df.columns and "longitud" in df.columns:
            assert df["latitud"].between(config.CABA_LAT_MIN, config.CABA_LAT_MAX).all()
            assert df["longitud"].between(config.CABA_LON_MIN, config.CABA_LON_MAX).all()
