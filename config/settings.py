"""Configuración centralizada y parámetros monetarios/geoespaciales del Capstone Project."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Datasets y geoespacial
DATASETS_DIR = BASE_DIR / "Datasets"
DATASETS_ORIGINALES_DIR = DATASETS_DIR / "Originales"
DATASETS_CURADOS_DIR = DATASETS_DIR / "Curados"

# ETL & Output
ETL_DIR = BASE_DIR / "etl"
ETL_OUTPUT_DIR = ETL_DIR / "output"
PRODUCTO1_DIR = ETL_OUTPUT_DIR  # Compatibilidad

# MLOps & Modelado
MLOPS_DIR = BASE_DIR / "mlops"
MLOPS_ARTIFACTS_DIR = MLOPS_DIR / "artifacts"
MLOPS_FIGURES_DIR = MLOPS_DIR / "figures"

# Aliases de compatibilidad para código y tests existentes
PRODUCTO2_DIR = MLOPS_DIR
PRODUCTO2_ARTIFACTS_DIR = MLOPS_ARTIFACTS_DIR
PRODUCTO2_FIGURES_DIR = MLOPS_FIGURES_DIR

EDA_DIR = BASE_DIR / "eda"


def _resolve_input(filename: str) -> Path:
    """Busca un archivo de entrada en Datasets/Originales o en la raíz del proyecto."""
    orig_path = DATASETS_ORIGINALES_DIR / filename
    if orig_path.exists():
        return orig_path
    root_path = BASE_DIR / filename
    if root_path.exists():
        return root_path
    return orig_path


# Rutas de entrada por defecto (parametrizables para nuevas extracciones)
ZONAPROP_PATH = _resolve_input("zonaprop_alquileres_caba_1000.json")
RUIDO_PATH = _resolve_input("medicion_de_ruido_diurno_2018.csv")
DELITOS_PATH = _resolve_input("delitos_2022.xlsx")
ESCUELAS_PATH = _resolve_input("establecimientos_educativos.xlsx")
SUBTE_PATH = _resolve_input("bocas-de-subte.csv")

# Rutas de salida (ETL output y reportes)
OUTPUT_CURATED_CSV = ETL_OUTPUT_DIR / "producto1_dataset_curado.csv"
OUTPUT_ENRICHED_CSV = ETL_OUTPUT_DIR / "dataset_enriquecido_completo.csv"
OUTPUT_EDA_JSON = ETL_OUTPUT_DIR / "eda_stats.json"
FIGURES_DIR = EDA_DIR / "figures"

# Parámetros configurables de unificación monetaria a ARS
TIPO_CAMBIO_BASE = 1200.0
FACTOR_IMPUESTOS_USD = 1.0
IMPUESTO_SELLOS_ALQUILER = 0.0

# Variable objetivo definida para MLOps
TARGET_COL = "costo_total_ars"

# Bounding box oficial aproximado de CABA (WGS84 EPSG:4326)
CABA_LAT_MIN = -34.72
CABA_LAT_MAX = -34.50
CABA_LON_MIN = -58.58
CABA_LON_MAX = -58.32

# Proyección local de CABA para establecimientos_educativos.xlsx
CABA_LOCAL_PROJ = (
    "+proj=tmerc +lat_0=-34.6297166 +lon_0=-58.4627 "
    "+k=0.999998 +x_0=20000 +y_0=70000 +ellps=intl +units=m +no_defs"
)

# Radio de tierra en metros para BallTree Haversine
EARTH_RADIUS_M = 6_371_000.0

# Pesos de gravedad delictiva para índice ponderado (delitos_2022.xlsx)
CRIME_WEIGHT_HOMICIDIO = 10.0
CRIME_WEIGHT_ARMA = 4.0
CRIME_WEIGHT_ROBO_LESIONES = 2.0
CRIME_WEIGHT_OTROS = 1.0

# Mapeo barrio -> comuna oficial CABA como respaldo
BARRIO_COMUNA_FALLBACK = {
    "Almagro": 5,
    "Balvanera": 3,
    "Belgrano": 13,
    "Caballito": 6,
    "Colegiales": 13,
    "Núñez": 13,
    "Nuñez": 13,
    "Palermo": 14,
    "Recoleta": 2,
    "Villa Devoto": 11,
    "Villa Urquiza": 12,
}
