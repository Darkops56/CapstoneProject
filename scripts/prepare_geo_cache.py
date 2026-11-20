"""Script para pre-procesar y comprimir los datos urbanos de GCBA en actor/reference_geo/."""

import csv
import sys
from pathlib import Path
import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
from shapely import wkt
from sklearn.neighbors import BallTree

BASE_DIR = Path(__file__).resolve().parent.parent
CURADOS_DIR = BASE_DIR / "Datasets" / "Curados"
OUTPUT_DIR = BASE_DIR / "actors" / "inference" / "reference_geo"


def _set_max_csv_field_limit() -> None:
    max_int = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_int)
            break
        except OverflowError:
            max_int = int(max_int / 10)


def build_geo_cache() -> None:
    """Genera los artefactos optimizados GeoParquet e índices BallTree."""
    _set_max_csv_field_limit()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Comprimir Ruido Curado a GeoParquet
    ruido_csv = CURADOS_DIR / "medicion_ruido_curado.csv"
    if not ruido_csv.exists():
        raise FileNotFoundError(f"No existe {ruido_csv}")
    print(f"Cargando {ruido_csv}...")
    ruido_df = pd.read_csv(ruido_csv)
    ruido_df["geometry"] = ruido_df["wkt"].apply(wkt.loads)
    gdf_ruido = gpd.GeoDataFrame(
        ruido_df[["comuna", "rango_db", "ruido_db_promedio", "geometry"]],
        geometry="geometry",
        crs="EPSG:4326",
    )
    ruido_parquet = OUTPUT_DIR / "medicion_ruido.parquet"
    gdf_ruido.to_parquet(ruido_parquet)
    print(f"Guardado GeoParquet de ruido en {ruido_parquet} ({len(gdf_ruido)} polígonos)")

    # 2. Generar BallTree e índice de Delitos
    delitos_csv = CURADOS_DIR / "delitos_2022_curado.csv"
    if not delitos_csv.exists():
        raise FileNotFoundError(f"No existe {delitos_csv}")
    print(f"Cargando {delitos_csv}...")
    del_df = pd.read_csv(delitos_csv).dropna(subset=["latitud", "longitud"])
    coords_rad = np.radians(del_df[["latitud", "longitud"]].to_numpy())
    del_tree = BallTree(coords_rad, metric="haversine")
    delitos_bundle = {
        "tree": del_tree,
        "cantidad": del_df["cantidad"].to_numpy(dtype=float),
        "peso_gravedad": del_df["peso_gravedad"].to_numpy(dtype=float),
    }
    delitos_path = OUTPUT_DIR / "delitos_tree.joblib"
    joblib.dump(delitos_bundle, delitos_path, compress=3)
    print(f"Guardado BallTree de delitos en {delitos_path} ({len(del_df)} registros)")

    # 3. Guardar Contexto Urbano (Escuelas y Subte)
    escuelas_csv = CURADOS_DIR / "establecimientos_educativos_curado.csv"
    subte_csv = CURADOS_DIR / "bocas_de_subte_curado.csv"

    esc_df = pd.read_csv(escuelas_csv).dropna(subset=["latitud", "longitud"])
    # Filtrar niveles familiares inicial, primario y secundario
    pattern = r"Nivel inicial|Nivel primario|Nivel secundario común"
    fam_mask = esc_df["nivel_educativo"].astype(str).str.contains(pattern, case=False, na=False, regex=True)
    esc_fam = esc_df.loc[fam_mask].copy()

    subte_df = pd.read_csv(subte_csv).dropna(subset=["latitud", "longitud"])

    # Guardar en contexto_urbano.parquet
    esc_fam_clean = esc_fam[["latitud", "longitud"]].copy()
    esc_fam_clean["tipo_referencia"] = "escuela"
    esc_fam_clean["linea"] = ""

    subte_clean = subte_df[["latitud", "longitud", "linea"]].copy()
    subte_clean["tipo_referencia"] = "subte"

    contexto_df = pd.concat([esc_fam_clean, subte_clean], ignore_index=True)
    contexto_path = OUTPUT_DIR / "contexto_urbano.parquet"
    contexto_df.to_parquet(contexto_path)
    print(f"Guardado contexto urbano en {contexto_path} ({len(contexto_df)} puntos)")


if __name__ == "__main__":
    build_geo_cache()
