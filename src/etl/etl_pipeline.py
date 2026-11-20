"""Pipeline ETL y enriquecimiento geoespacial para los 5 datasets locales de CABA."""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt
from sklearn.neighbors import BallTree

from config import settings as config


def _set_max_csv_field_limit() -> None:
    """Configura el límite máximo de campo CSV (compatible con Windows 64-bit)."""
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2_147_483_647)


def normalize_caba_coord(val: Any, min_val: float, max_val: float) -> float:
    """Normaliza coordenadas con punto decimal desplazado dividiendo por 10 hasta el rango CABA."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return np.nan
    try:
        if isinstance(val, str):
            val = val.strip().replace(",", ".")
            if not val:
                return np.nan
        num = float(val)
    except (TypeError, ValueError):
        return np.nan

    if not np.isfinite(num) or num == 0.0:
        return np.nan
    if min_val <= num <= max_val:
        return num

    # Si es positivo pero su negativo coincide con el rango CABA, no inventamos signo salvo rango explícito
    abs_num = abs(num)
    if num > 0:
        return np.nan

    # Dividir sucesivamente por 10 si la magnitud está desplazada (ej. -34584136 o -3.46e16)
    temp = num
    for _ in range(25):
        if min_val <= temp <= max_val:
            return temp
        if abs(temp) < abs(max_val):
            break
        temp /= 10.0

    # Caso borde: magnitud menor por desplazamiento inverso (raro, multiplicamos por 10)
    temp = num
    for _ in range(5):
        if min_val <= temp <= max_val:
            return temp
        if abs(temp) > abs(min_val):
            break
        temp *= 10.0

    _ = abs_num
    return np.nan


def _parse_ar_number(raw: str) -> float:
    """Convierte montos con formato argentino ('1.200.000', '172.000', '382000,50') a float."""
    s = raw.strip().rstrip(".,-")
    if not s:
        return np.nan
    # Si tiene coma decimal y puntos de miles: 1.200.000,50 -> 1200000.50
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            s = "".join(parts)
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_price_ars(
    amount: Any,
    currency: str | None,
    tipo_cambio: float = config.TIPO_CAMBIO_BASE,
    factor_usd: float = config.FACTOR_IMPUESTOS_USD,
    sellos: float = config.IMPUESTO_SELLOS_ALQUILER,
) -> float:
    """Unifica precios en USD o ARS a Pesos Argentinos (ARS) con parámetros configurables."""
    if amount is None or (isinstance(amount, float) and np.isnan(amount)):
        return np.nan
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return np.nan
    if val <= 0:
        return np.nan

    curr = (currency or "ARS").strip().upper()
    if curr in {"USD", "U$S", "U$D", "DOLAR", "DOLARES"}:
        ars = val * tipo_cambio * factor_usd
    else:
        ars = val
    return ars * (1.0 + sellos)


def _extract_first_int(text: str | None) -> float:
    """Extrae el primer entero de una cadena como '95 m² cub.' o '3 amb.'."""
    if not text:
        return np.nan
    m = re.search(r"(\d+)", str(text))
    return float(m.group(1)) if m else np.nan


def _parse_main_features(item: dict[str, Any]) -> dict[str, float]:
    """Extrae características físicas principales desde mainFeatures (y respaldo en featuresListCardSimplified)."""
    mf_map: dict[str, str] = {}
    for entry in (item.get("featuresListCardSimplified") or []):
        fid = entry.get("featureId")
        if fid and entry.get("value"):
            mf_map[str(fid)] = str(entry["value"])
    for entry in (item.get("mainFeatures") or []):
        fid = entry.get("id")
        if fid and entry.get("value"):
            mf_map[str(fid)] = str(entry["value"])

    cft5_raw = mf_map.get("CFT5", "")
    if "estrenar" in cft5_raw.lower():
        antiguedad = 0.0
        es_a_estrenar = 1
    else:
        antiguedad = _extract_first_int(cft5_raw)
        es_a_estrenar = 1 if antiguedad == 0 else 0

    return {
        "m2_cubiertos": _extract_first_int(mf_map.get("CFT101")),
        "m2_totales": _extract_first_int(mf_map.get("CFT100")),
        "ambientes": _extract_first_int(mf_map.get("CFT1")),
        "dormitorios": _extract_first_int(mf_map.get("CFT2")),
        "banos": _extract_first_int(mf_map.get("CFT3")),
        "toilettes": _extract_first_int(mf_map.get("CFT4")),
        "cocheras": _extract_first_int(mf_map.get("CFT7")) if "CFT7" in mf_map else 0.0,
        "antiguedad_anios": antiguedad,
        "es_a_estrenar": float(es_a_estrenar),
    }


def extract_expenses_ars(
    item: dict[str, Any],
    tipo_cambio: float = config.TIPO_CAMBIO_BASE,
    factor_usd: float = config.FACTOR_IMPUESTOS_USD,
) -> tuple[float, str]:
    """Extrae expensas desde campos estructurados o regex sobre descripción."""
    prices = item.get("prices") or {}
    for dp in (prices.get("detailPricesArray") or []):
        exp_str = dp.get("expenses")
        if exp_str:
            m = re.search(r"(USD|U\$S|\$)?\s*([\d.,]+)", str(exp_str), re.I)
            if m:
                val = _parse_ar_number(m.group(2))
                if not np.isnan(val) and val >= 0:
                    if m.group(1) and m.group(1).upper() in {"USD", "U$S"}:
                        val = val * tipo_cambio * factor_usd
                    return val, "structured"

    desc = f"{item.get('description') or ''} {item.get('list_description') or ''}"
    if re.search(r"(?:expensas\s+incluidas|incluye\s+expensas|sin\s+expensas)", desc, re.I):
        return 0.0, "included_in_rent"

    # Buscar montos que aparezcan DESPUÉS de la palabra expensas (ej. 'EXPENSAS (oct 26) $ 172.000')
    m_desc = re.search(
        r"expensas\b[^$\n]{0,35}?(?:(usd|u\$s)\s*|(?:\$|ars)\s*)([\d]{1,3}(?:\.[\d]{3})+|\d{4,7})",
        desc,
        re.I,
    )
    if m_desc:
        val = _parse_ar_number(m_desc.group(2))
        if not np.isnan(val) and val > 0:
            if m_desc.group(1):
                val = val * tipo_cambio * factor_usd
            return val, "regex_desc"

    return np.nan, "missing"


def extract_apto_mascotas(item: dict[str, Any], return_reason: bool = False) -> int | tuple[int, str]:
    """Determina apto_mascotas (0/1) combinando pills, features y reglas NLP con negaciones."""
    desc = f"{item.get('description') or ''} {item.get('list_description') or ''} {item.get('title') or ''}"

    pills = (item.get("detailExtraTopLevel") or {}).get("pills") or []
    features = item.get("featuresListCardSimplified") or []
    struct_yes = any(p.get("id") == "ADMITS_PETS" for p in pills) or any(
        str(fl.get("featureId")) == "1000002" or "permite mascotas" in str(fl.get("featureLabel", "")).lower()
        for fl in features
    )

    # 1. La negación explícita en la descripción tiene prioridad sobre etiquetas genéricas
    if re.search(
        r"\bno\s+(?:se\s+)?(?:acepta\w*|permit\w*|admit\w*)\s+mascotas?\b|\bprohibid\w*\s+mascotas?\b|\bsin\s+mascotas?\b",
        desc,
        re.I,
    ):
        reason = "nlp_negation_override" if struct_yes else "nlp_negation"
        return (0, reason) if return_reason else 0

    # 2. Señal estructurada explícita
    if struct_yes:
        return (1, "structured") if return_reason else 1

    # 3. Señal positiva en descripción
    if re.search(r"\b(?:apto|acepta\w*|permit\w*|admit\w*)\s+mascotas?\b|\bpet\s*friendly\b", desc, re.I):
        return (1, "nlp_positive") if return_reason else 1

    return (0, "not_specified") if return_reason else 0


def extract_amenities(item: dict[str, Any]) -> dict[str, float]:
    """Extrae amenities binarios y scores ponderados (general, soltero/ejecutivo, familia)."""
    features = item.get("featuresListCardSimplified") or []
    f_ids = {str(fl.get("featureId")) for fl in features if fl.get("featureId")}
    f_labels = " ".join(str(fl.get("featureLabel") or "") for fl in features).lower()
    desc = f"{item.get('description') or ''} {item.get('list_description') or ''}".lower()
    text_all = f"{f_labels} {desc}"

    mf = _parse_main_features(item)

    has_gimnasio = int("1000068" in f_ids or bool(re.search(r"\bgimnasio\b|\bgym\b|\bfitness\b", text_all)))
    has_pileta = int("1000079" in f_ids or bool(re.search(r"\bpileta\b|\bpiscina\b|\bswimming\b", text_all)))
    has_parrilla = int("1000078" in f_ids or "1000085" in f_ids or bool(re.search(r"\bparrilla\b|\bquincho\b", text_all)))
    has_sum = int("1000092" in f_ids or bool(re.search(r"\bsum\b|\bcoworking\b|\bco-working\b|\bsal[oó]n de usos\b", text_all)))
    has_seguridad = int(
        "1000097" in f_ids
        or "2000142" in f_ids
        or "1000039" in f_ids
        or bool(re.search(r"\bseguridad\b|\bvigilancia\b|\btótem\b|\btotem\b|\b24\s*hs\b|\b24\s*horas\b|\bencargado\b", text_all))
    )
    has_balcon_terraza = int(
        "1000100" in f_ids
        or "1000116" in f_ids
        or "1000114" in f_ids
        or bool(re.search(r"\bbalc[oó]n\b|\bterraza\b|\bpatio\b", text_all))
    )
    has_cochera = int(
        (mf["cocheras"] > 0)
        or "1000018" in f_ids
        or (bool(re.search(r"\bcochera\b|\bgarage\b", text_all)) and not bool(re.search(r"\bsin\s+cochera\b", text_all)))
    )

    # Ponderación diferenciada (normalizada en escala 0..10)
    # Solteros/Ejecutivos valoran más Gym, SUM/Coworking, Balcón, Seguridad
    score_soltero = (
        2.5 * has_gimnasio
        + 2.0 * has_sum
        + 1.5 * has_balcon_terraza
        + 1.5 * has_seguridad
        + 1.0 * has_pileta
        + 0.75 * has_parrilla
        + 0.75 * has_cochera
    )
    # Familias valoran más Seguridad, Cochera, Pileta, Parrilla, Balcón/Terraza
    score_familia = (
        2.5 * has_seguridad
        + 2.0 * has_cochera
        + 1.5 * has_pileta
        + 1.5 * has_parrilla
        + 1.25 * has_balcon_terraza
        + 0.75 * has_sum
        + 0.5 * has_gimnasio
    )
    # Score compuesto balanceado 0..10
    score_general = round(
        (
            1.5 * has_seguridad
            + 1.5 * has_cochera
            + 1.5 * has_pileta
            + 1.5 * has_gimnasio
            + 1.5 * has_parrilla
            + 1.5 * has_sum
            + 1.0 * has_balcon_terraza
        ),
        2,
    )

    return {
        "has_gimnasio": has_gimnasio,
        "has_pileta": has_pileta,
        "has_parrilla": has_parrilla,
        "has_sum_coworking": has_sum,
        "has_seguridad": has_seguridad,
        "has_balcon_terraza": has_balcon_terraza,
        "has_cochera": has_cochera,
        "score_amenities_soltero": round(score_soltero, 2),
        "score_amenities_familia": round(score_familia, 2),
        "score_amenities": score_general,
    }


def _extract_barrio_subzona(item: dict[str, Any]) -> tuple[str, str]:
    """Normaliza macro-barrio oficial CABA y sub-zona desde location.neighborhood / list_location_label."""
    loc = item.get("location") or {}
    raw = str(loc.get("neighborhood") or item.get("list_location_label") or "").strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 2 and parts[-1].lower() in {"capital federal", "caba", "buenos aires"}:
        barrio = parts[-2]
        subzona = parts[0] if len(parts) >= 3 else barrio
    elif parts:
        barrio = parts[-1]
        subzona = parts[0]
    else:
        barrio, subzona = "Desconocido", "Desconocido"
    return barrio, subzona


def load_and_clean_zonaprop(
    zonaprop_path: Path | str = config.ZONAPROP_PATH,
    tipo_cambio: float = config.TIPO_CAMBIO_BASE,
    factor_usd: float = config.FACTOR_IMPUESTOS_USD,
    sellos: float = config.IMPUESTO_SELLOS_ALQUILER,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Carga JSON de Zonaprop, unifica moneda, extrae features NLP y limpia registros inválidos."""
    with open(zonaprop_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    records = []
    for it in raw_items:
        loc = it.get("location") or {}
        lat_raw = it.get("list_latitude")
        lon_raw = it.get("list_longitude")
        ubic_aprox = 0
        if lat_raw is None or lon_raw is None:
            lat_raw = loc.get("latitude")
            lon_raw = loc.get("longitude")
            ubic_aprox = 1

        alquiler_ars = parse_price_ars(
            it.get("list_price_amount"),
            it.get("list_price_currency"),
            tipo_cambio=tipo_cambio,
            factor_usd=factor_usd,
            sellos=sellos,
        )
        exp_val, exp_src = extract_expenses_ars(it, tipo_cambio=tipo_cambio, factor_usd=factor_usd)
        pet_val, pet_reason = extract_apto_mascotas(it, return_reason=True)
        mf = _parse_main_features(it)
        am = extract_amenities(it)
        barrio, subzona = _extract_barrio_subzona(it)

        records.append(
            {
                "listing_id": str(it.get("listingId")),
                "latitud": float(lat_raw) if lat_raw is not None else np.nan,
                "longitud": float(lon_raw) if lon_raw is not None else np.nan,
                "ubicacion_aproximada": ubic_aprox,
                "barrio": barrio,
                "subzona": subzona,
                "moneda_origen": str(it.get("list_price_currency") or "ARS"),
                "precio_origen": it.get("list_price_amount"),
                "alquiler_ars": alquiler_ars,
                "expensas_ars": exp_val,
                "expensas_fuente": exp_src,
                "apto_mascotas": pet_val,
                "mascotas_fuente": pet_reason,
                **mf,
                **am,
            }
        )

    df = pd.DataFrame(records)
    audit: dict[str, Any] = {"raw_records": int(len(df))}

    # Deduplicar por listing_id
    dups = int(df.duplicated(subset=["listing_id"]).sum())
    df = df.drop_duplicates(subset=["listing_id"], keep="first").reset_index(drop=True)
    audit["duplicates_removed"] = dups

    # Filtrar precios inválidos (<= 0 o NaN)
    invalid_price_mask = df["alquiler_ars"].isna() | (df["alquiler_ars"] <= 0)
    audit["dropped_invalid_price"] = int(invalid_price_mask.sum())
    df = df.loc[~invalid_price_mask].copy()

    # Filtrar coordenadas fuera del bounding box de CABA o nulas
    in_caba = (
        df["latitud"].between(config.CABA_LAT_MIN, config.CABA_LAT_MAX)
        & df["longitud"].between(config.CABA_LON_MIN, config.CABA_LON_MAX)
    )
    audit["dropped_out_of_caba_coords"] = int((~in_caba).sum())
    audit["out_of_caba_listing_ids"] = df.loc[~in_caba, "listing_id"].tolist()
    df = df.loc[in_caba].copy().reset_index(drop=True)

    # Reparar / imputar dimensiones físicas (m2_totales, m2_cubiertos, dormitorios, banos, antiguedad)
    nulos_antes = df[["m2_totales", "m2_cubiertos", "ambientes", "dormitorios", "banos", "antiguedad_anios", "expensas_ars"]].isna().sum().to_dict()
    audit["missing_before_imputation"] = {k: int(v) for k, v in nulos_antes.items()}

    # Si falta m2_totales, usar m2_cubiertos; si falta m2_cubiertos, usar ratio mediano cubierto/total * m2_totales
    ratio_cub_tot = (df["m2_cubiertos"] / df["m2_totales"]).replace([np.inf, -np.inf], np.nan).median()
    if pd.isna(ratio_cub_tot) or not (0.5 <= ratio_cub_tot <= 1.0):
        ratio_cub_tot = 0.90
    df["m2_totales"] = df["m2_totales"].fillna(df["m2_cubiertos"])
    df["m2_cubiertos"] = df["m2_cubiertos"].fillna((df["m2_totales"] * ratio_cub_tot).round(0))

    # Filtrar registros sin superficie válida tras recuperación
    invalid_m2 = df["m2_totales"].isna() | (df["m2_totales"] <= 10) | (df["m2_totales"] > 2000)
    audit["dropped_invalid_m2"] = int(invalid_m2.sum())
    df = df.loc[~invalid_m2].copy().reset_index(drop=True)

    # Coherencia m2_cubiertos <= m2_totales
    incoherent_m2 = df["m2_cubiertos"] > df["m2_totales"]
    audit["fixed_covered_gt_total_m2"] = int(incoherent_m2.sum())
    df.loc[incoherent_m2, "m2_cubiertos"] = df.loc[incoherent_m2, "m2_totales"]

    # Ambientes, dormitorios, baños, antigüedad
    df["ambientes"] = df["ambientes"].fillna(df["ambientes"].median()).clip(lower=1)
    # Monoambientes suelen no declarar CFT2 (dormitorios); si ambientes == 1 -> 0 dorm, si > 1 -> ambientes - 1
    missing_dorm = df["dormitorios"].isna()
    df.loc[missing_dorm, "dormitorios"] = (df.loc[missing_dorm, "ambientes"] - 1).clip(lower=0)
    df["banos"] = df["banos"].fillna(df.groupby("ambientes")["banos"].transform("median")).fillna(1.0)
    df["antiguedad_anios"] = df["antiguedad_anios"].fillna(df.groupby("barrio")["antiguedad_anios"].transform("median")).fillna(df["antiguedad_anios"].median())
    df["toilettes"] = df["toilettes"].fillna(0.0)

    # Imputación de expensas: mediana de expensas/m2 por barrio * m2_totales (con bandera de imputación)
    df["expensas_imputadas"] = df["expensas_ars"].isna().astype(int)
    valid_exp = df["expensas_ars"].notna() & (df["expensas_ars"] > 0)
    exp_m2 = pd.Series(np.nan, index=df.index)
    exp_m2.loc[valid_exp] = df.loc[valid_exp, "expensas_ars"] / df.loc[valid_exp, "m2_totales"]

    med_exp_m2_barrio = exp_m2.groupby(df["barrio"]).transform("median")
    global_med_exp_m2 = float(exp_m2.median()) if exp_m2.notna().any() else 2500.0
    med_exp_m2_barrio = med_exp_m2_barrio.fillna(global_med_exp_m2)

    df.loc[df["expensas_ars"].isna(), "expensas_ars"] = (
        df.loc[df["expensas_ars"].isna(), "m2_totales"] * med_exp_m2_barrio.loc[df["expensas_ars"].isna()]
    ).round(0)
    df["expensas_ars"] = df["expensas_ars"].clip(lower=0.0)

    # Targets y métricas derivadas de precio
    df["costo_total_ars"] = df["alquiler_ars"] + df["expensas_ars"]
    df["precio_m2_total_ars"] = df["costo_total_ars"] / df["m2_totales"]
    df["precio_m2_cubierto_ars"] = df["costo_total_ars"] / df["m2_cubiertos"].clip(lower=1.0)

    audit["expensas_source_counts"] = df["expensas_fuente"].value_counts().to_dict()
    audit["mascotas_source_counts"] = df["mascotas_fuente"].value_counts().to_dict()
    audit["imputed_counts"] = {
        "expensas_ars": int(df["expensas_imputadas"].sum()),
        "dormitorios": int(missing_dorm.sum()),
        "antiguedad_anios": int(nulos_antes["antiguedad_anios"]),
        "banos": int(nulos_antes["banos"]),
    }
    audit["valid_properties_after_etl"] = int(len(df))
    return df, audit


def _prepare_ruido_gdf(ruido_path: Path | str) -> gpd.GeoDataFrame:
    """Carga y valida polígonos de ruido diurno en EPSG:4326 con ruido_db_promedio."""
    _set_max_csv_field_limit()
    ruido_df = pd.read_csv(ruido_path)
    ruido_df["geometry"] = ruido_df["wkt"].apply(wkt.loads)
    ruido_df["ruido_db_promedio"] = (
        ruido_df["limite_inferior_rango_db"].astype(float)
        + ruido_df["limite_superior_rango_db"].astype(float)
    ) / 2.0
    return gpd.GeoDataFrame(ruido_df, geometry="geometry", crs="EPSG:4326")


def _prepare_delitos_df(delitos_path: Path | str) -> tuple[pd.DataFrame, dict[str, int]]:
    """Carga delitos_2022.xlsx, normaliza coordenadas CABA y calcula peso_gravedad."""
    delitos = pd.read_excel(delitos_path)
    raw_count = int(len(delitos))
    null_coords = int((delitos["latitud"].isna() | delitos["longitud"].isna()).sum())

    delitos["lat_norm"] = delitos["latitud"].apply(
        lambda v: normalize_caba_coord(v, config.CABA_LAT_MIN, config.CABA_LAT_MAX)
    )
    delitos["lon_norm"] = delitos["longitud"].apply(
        lambda v: normalize_caba_coord(v, config.CABA_LON_MIN, config.CABA_LON_MAX)
    )

    valid_del = delitos.dropna(subset=["lat_norm", "lon_norm"]).copy()
    unrecoverable = int(raw_count - len(valid_del) - null_coords)

    tipo_str = valid_del["tipo"].astype(str).str.strip().str.lower()
    arma_si = valid_del["uso_arma"].astype(str).str.strip().str.upper() == "SI"
    cant = pd.to_numeric(valid_del["cantidad"], errors="coerce").fillna(1.0).clip(lower=1.0)

    base_weight = np.where(
        tipo_str == "homicidios",
        config.CRIME_WEIGHT_HOMICIDIO,
        np.where(
            arma_si,
            config.CRIME_WEIGHT_ARMA,
            np.where(
                tipo_str.isin(["robo", "lesiones"]),
                config.CRIME_WEIGHT_ROBO_LESIONES,
                config.CRIME_WEIGHT_OTROS,
            ),
        ),
    )
    valid_del["peso_gravedad"] = base_weight * cant
    valid_del["es_robo_hurto"] = tipo_str.isin(["robo", "hurto"]).astype(float) * cant
    valid_del["cantidad_clean"] = cant

    audit = {
        "delitos_raw_rows": raw_count,
        "delitos_null_coords": null_coords,
        "delitos_unrecoverable_coords": unrecoverable,
        "delitos_valid_rows": int(len(valid_del)),
    }
    return valid_del, audit


def _prepare_escuelas_gdf(escuelas_path: Path | str) -> tuple[gpd.GeoDataFrame, int]:
    """Carga establecimientos_educativos.xlsx, reproyecta a EPSG:4326 y filtra niveles familiares."""
    esc = pd.read_excel(escuelas_path)
    raw_count = int(len(esc))
    esc["geometry"] = esc["geometry"].apply(wkt.loads)
    gdf_esc = gpd.GeoDataFrame(esc, geometry="geometry", crs=config.CABA_LOCAL_PROJ).to_crs("EPSG:4326")
    gdf_esc["lat"] = gdf_esc.geometry.y
    gdf_esc["lon"] = gdf_esc.geometry.x

    pattern = r"Nivel inicial|Nivel primario|Nivel secundario común"
    fam_mask = gdf_esc["nen_mde"].astype(str).str.contains(pattern, case=False, na=False, regex=True)
    gdf_fam = gdf_esc.loc[fam_mask].dropna(subset=["lat", "lon"]).copy()
    return gdf_fam, raw_count


def enrich_with_noise(
    df: pd.DataFrame,
    ruido_path: Path | str = config.RUIDO_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Asigna nivel de ruido diurno (dBA) vía GeoPandas sjoin(within) con fallback sjoin_nearest."""
    gdf_ruido = _prepare_ruido_gdf(ruido_path)[["ruido_db_promedio", "comuna", "rango_db", "geometry"]]

    gdf_props = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["longitud"], df["latitud"]),
        crs="EPSG:4326",
    )

    # Spatial join principal: within
    joined = gpd.sjoin(gdf_props, gdf_ruido, how="left", predicate="within")
    # Si algún punto cae exactamente en un borde compartido por 2 polígonos, promediar dB y tomar primer comuna
    if joined.index.duplicated().any():
        joined = joined.groupby(joined.index).agg(
            {
                **{c: "first" for c in df.columns},
                "geometry": "first",
                "ruido_db_promedio": "mean",
                "comuna": "first",
                "rango_db": "first",
            }
        )
        joined = gpd.GeoDataFrame(joined, geometry="geometry", crs="EPSG:4326")

    missing_mask = joined["ruido_db_promedio"].isna()
    n_nearest = int(missing_mask.sum())

    if n_nearest > 0:
        # Proyectar temporalmente a proyección métrica local de CABA para sjoin_nearest exacto en metros
        sub_missing = gdf_props.loc[missing_mask, ["listing_id", "geometry"]].to_crs(config.CABA_LOCAL_PROJ)
        ruido_proj = gdf_ruido.to_crs(config.CABA_LOCAL_PROJ)
        nearest = gpd.sjoin_nearest(sub_missing, ruido_proj, how="left", distance_col="dist_poligono_ruido_m")
        nearest = nearest.groupby(nearest.index).first()
        joined.loc[missing_mask, "ruido_db_promedio"] = nearest["ruido_db_promedio"].values
        joined.loc[missing_mask, "comuna"] = nearest["comuna"].values
        joined.loc[missing_mask, "rango_db"] = nearest["rango_db"].values

    out = pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))
    # Respaldo comuna si quedara nulo
    out["comuna"] = pd.to_numeric(out["comuna"], errors="coerce")
    out["comuna"] = out["comuna"].fillna(out["barrio"].map(config.BARRIO_COMUNA_FALLBACK)).fillna(0).astype(int)
    out["ruido_imputado_nearest"] = missing_mask.astype(int).values

    return out, {
        "ruido_polygons": int(len(gdf_ruido)),
        "matched_within": int(len(df) - n_nearest),
        "imputed_nearest": n_nearest,
    }


def enrich_with_crime(
    df: pd.DataFrame,
    delitos_path: Path | str = config.DELITOS_PATH,
    radius_m: float = 500.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normaliza coordenadas desplazadas de delitos_2022.xlsx y calcula densidad e índice ponderado a 500m."""
    valid_del, audit = _prepare_delitos_df(delitos_path)

    tree = BallTree(np.radians(valid_del[["lat_norm", "lon_norm"]].to_numpy()), metric="haversine")
    prop_coords_rad = np.radians(df[["latitud", "longitud"]].to_numpy())
    neighbors = tree.query_radius(prop_coords_rad, r=radius_m / config.EARTH_RADIUS_M)

    cant_arr = valid_del["cantidad_clean"].to_numpy()
    robo_hurto_arr = valid_del["es_robo_hurto"].to_numpy()
    grav_arr = valid_del["peso_gravedad"].to_numpy()

    out = df.copy()
    out["densidad_delitos_500m"] = [float(cant_arr[idx].sum()) for idx in neighbors]
    out["densidad_robos_500m"] = [float(robo_hurto_arr[idx].sum()) for idx in neighbors]
    out["indice_gravedad_delitos_500m"] = [float(grav_arr[idx].sum()) for idx in neighbors]

    return out, audit


def enrich_with_schools(
    df: pd.DataFrame,
    escuelas_path: Path | str = config.ESCUELAS_PATH,
    radius_m: float = 500.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Reproyecta escuelas de proyección local CABA a EPSG:4326, filtra niveles familiares y calcula BallTree 500m."""
    gdf_fam, raw_count = _prepare_escuelas_gdf(escuelas_path)

    tree = BallTree(np.radians(gdf_fam[["lat", "lon"]].to_numpy()), metric="haversine")
    prop_coords_rad = np.radians(df[["latitud", "longitud"]].to_numpy())

    counts = tree.query_radius(prop_coords_rad, r=radius_m / config.EARTH_RADIUS_M, count_only=True)
    dists_rad, _ = tree.query(prop_coords_rad, k=1)

    out = df.copy()
    out["escuelas_familias_500m"] = counts.astype(int)
    out["distancia_escuela_m"] = (dists_rad[:, 0] * config.EARTH_RADIUS_M).round(2)

    return out, {
        "escuelas_raw_rows": raw_count,
        "escuelas_familias_filtered": int(len(gdf_fam)),
        "reprojected_bounds_lat": [float(gdf_fam["lat"].min()), float(gdf_fam["lat"].max())],
        "reprojected_bounds_lon": [float(gdf_fam["lon"].min()), float(gdf_fam["lon"].max())],
    }


def enrich_with_subte(
    df: pd.DataFrame,
    subte_path: Path | str = config.SUBTE_PATH,
    radius_m: float = 600.0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Calcula distancia mínima al subte (m) y cantidad de líneas distintas a menos de 600m."""
    subte = pd.read_csv(subte_path).dropna(subset=["lat", "long"]).copy()
    tree = BallTree(np.radians(subte[["lat", "long"]].to_numpy()), metric="haversine")
    prop_coords_rad = np.radians(df[["latitud", "longitud"]].to_numpy())

    dists_rad, _ = tree.query(prop_coords_rad, k=1)
    neighbors = tree.query_radius(prop_coords_rad, r=radius_m / config.EARTH_RADIUS_M)

    lineas_arr = subte["linea"].astype(str).str.strip().to_numpy()
    lineas_distintas = [int(len(set(lineas_arr[idx]))) for idx in neighbors]

    out = df.copy()
    out["distancia_subte_m"] = (dists_rad[:, 0] * config.EARTH_RADIUS_M).round(2)
    out["lineas_subte_600m"] = lineas_distintas

    return out, {
        "subte_bocas_count": int(len(subte)),
        "unique_lines_total": sorted(subte["linea"].astype(str).str.strip().unique().tolist()),
    }


def detect_outliers_iqr_zscore(df: pd.DataFrame, cols: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Detecta outliers mediante IQR (1.5*IQR) y Z-score (|z| > 3) dejando banderas para auditoría."""
    out = df.copy()
    summary: dict[str, Any] = {}

    for col in cols:
        s = out[col].astype(float)
        q1, q3 = float(s.quantile(0.25)), float(s.quantile(0.75))
        iqr = q3 - q1
        low_iqr, high_iqr = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flag_iqr = (s < low_iqr) | (s > high_iqr)

        std = float(s.std(ddof=1))
        z = (s - float(s.mean())) / std if std > 0 else pd.Series(0.0, index=s.index)
        flag_z = z.abs() > 3.0

        out[f"outlier_iqr_{col}"] = flag_iqr.astype(int)
        out[f"outlier_zscore_{col}"] = flag_z.astype(int)
        summary[col] = {
            "Q1": round(q1, 2),
            "Q3": round(q3, 2),
            "IQR": round(iqr, 2),
            "lower_bound_iqr": round(low_iqr, 2),
            "upper_bound_iqr": round(high_iqr, 2),
            "outliers_iqr_count": int(flag_iqr.sum()),
            "outliers_iqr_pct": round(float(flag_iqr.mean() * 100.0), 2),
            "outliers_zscore_count": int(flag_z.sum()),
            "outliers_zscore_pct": round(float(flag_z.mean() * 100.0), 2),
        }

    return out, summary


def run_full_etl(
    zonaprop_path: Path | str = config.ZONAPROP_PATH,
    ruido_path: Path | str = config.RUIDO_PATH,
    delitos_path: Path | str = config.DELITOS_PATH,
    escuelas_path: Path | str = config.ESCUELAS_PATH,
    subte_path: Path | str = config.SUBTE_PATH,
    tipo_cambio: float = config.TIPO_CAMBIO_BASE,
    factor_usd: float = config.FACTOR_IMPUESTOS_USD,
    sellos: float = config.IMPUESTO_SELLOS_ALQUILER,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Ejecuta el pipeline ETL completo sobre los 5 archivos locales y retorna DataFrame + auditoría."""
    df, audit_zp = load_and_clean_zonaprop(
        zonaprop_path=zonaprop_path,
        tipo_cambio=tipo_cambio,
        factor_usd=factor_usd,
        sellos=sellos,
    )
    df, audit_ruido = enrich_with_noise(df, ruido_path=ruido_path)
    df, audit_delitos = enrich_with_crime(df, delitos_path=delitos_path)
    df, audit_escuelas = enrich_with_schools(df, escuelas_path=escuelas_path)
    df, audit_subte = enrich_with_subte(df, subte_path=subte_path)

    df, outlier_audit = detect_outliers_iqr_zscore(
        df,
        cols=["costo_total_ars", "precio_m2_total_ars", "m2_totales"],
    )

    audit = {
        "zonaprop": audit_zp,
        "ruido": audit_ruido,
        "delitos": audit_delitos,
        "escuelas": audit_escuelas,
        "subte": audit_subte,
        "outliers": outlier_audit,
        "final_rows": int(len(df)),
    }
    return df, audit


def export_all_curated_datasets(
    output_dir: Path | str = config.DATASETS_CURADOS_DIR,
) -> dict[str, dict[str, Any]]:
    """Exporta los 5 datasets individuales curados en formato .csv unificado (WGS84 EPSG:4326)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, Any]] = {}

    # 1. Zonaprop curado
    df_zp, _ = load_and_clean_zonaprop()
    p_zp = out_dir / "zonaprop_alquileres_curado.csv"
    df_zp.to_csv(p_zp, index=False, encoding="utf-8")
    summary["zonaprop_alquileres_curado.csv"] = {"rows": int(len(df_zp)), "cols": int(df_zp.shape[1])}

    # 2. Medición de ruido diurno curado (EPSG:4326)
    gdf_ruido = _prepare_ruido_gdf(config.RUIDO_PATH)
    df_ruido_out = pd.DataFrame(
        {
            "comuna": pd.to_numeric(gdf_ruido["comuna"], errors="coerce").fillna(0).astype(int),
            "rango_db": gdf_ruido["rango_db"],
            "limite_inferior_rango_db": gdf_ruido["limite_inferior_rango_db"].astype(float),
            "limite_superior_rango_db": gdf_ruido["limite_superior_rango_db"].astype(float),
            "ruido_db_promedio": gdf_ruido["ruido_db_promedio"].astype(float),
            "leyenda": gdf_ruido["leyenda"],
            "periodo": gdf_ruido["periodo"],
            "wkt": gdf_ruido["wkt"],
        }
    )
    p_ruido = out_dir / "medicion_ruido_curado.csv"
    df_ruido_out.to_csv(p_ruido, index=False, encoding="utf-8")
    summary["medicion_ruido_curado.csv"] = {"rows": int(len(df_ruido_out)), "cols": int(df_ruido_out.shape[1])}

    # 3. Delitos 2022 curado (coordenadas normalizadas EPSG:4326)
    df_del, _ = _prepare_delitos_df(config.DELITOS_PATH)
    df_del_out = pd.DataFrame(
        {
            "id_mapa": df_del["id-mapa"],
            "anio": df_del["anio"],
            "mes": df_del["mes"],
            "dia": df_del["dia"],
            "franja": df_del["franja"],
            "tipo": df_del["tipo"],
            "subtipo": df_del["subtipo"],
            "uso_arma": df_del["uso_arma"],
            "uso_moto": df_del["uso_moto"],
            "barrio": df_del["barrio"],
            "comuna": pd.to_numeric(df_del["comuna"], errors="coerce").fillna(0).astype(int),
            "latitud": df_del["lat_norm"].round(6),
            "longitud": df_del["lon_norm"].round(6),
            "cantidad": df_del["cantidad_clean"].astype(int),
            "peso_gravedad": df_del["peso_gravedad"],
        }
    )
    p_del = out_dir / "delitos_2022_curado.csv"
    df_del_out.to_csv(p_del, index=False, encoding="utf-8")
    summary["delitos_2022_curado.csv"] = {"rows": int(len(df_del_out)), "cols": int(df_del_out.shape[1])}

    # 4. Establecimientos educativos curado (reproyectado a EPSG:4326 y filtrado niveles familiares)
    gdf_esc, _ = _prepare_escuelas_gdf(config.ESCUELAS_PATH)
    df_esc_out = pd.DataFrame(
        {
            "id": gdf_esc["id"],
            "nombre": gdf_esc["nam"],
            "gestion": gdf_esc["ges"].fillna("Sin especificar"),
            "nivel_educativo": gdf_esc["nen_mde"],
            "tipo": gdf_esc["tip"],
            "direccion": gdf_esc["dir"],
            "barrio": gdf_esc["bar"],
            "comuna": pd.to_numeric(gdf_esc["com"], errors="coerce").fillna(0).astype(int),
            "latitud": gdf_esc["lat"].round(6),
            "longitud": gdf_esc["lon"].round(6),
        }
    )
    p_esc = out_dir / "establecimientos_educativos_curado.csv"
    df_esc_out.to_csv(p_esc, index=False, encoding="utf-8")
    summary["establecimientos_educativos_curado.csv"] = {"rows": int(len(df_esc_out)), "cols": int(df_esc_out.shape[1])}

    # 5. Bocas de subte curado (EPSG:4326 unificado)
    subte = pd.read_csv(config.SUBTE_PATH).dropna(subset=["lat", "long"]).copy()
    df_subte_out = subte.rename(columns={"lat": "latitud", "long": "longitud"})[
        [
            "id",
            "linea",
            "estacion",
            "destino_bo",
            "lineas_de_",
            "barrio",
            "comuna",
            "calle",
            "altura",
            "ascensor",
            "escalera_m",
            "rampa",
            "latitud",
            "longitud",
        ]
    ].copy()
    df_subte_out["linea"] = df_subte_out["linea"].astype(str).str.strip()
    p_subte = out_dir / "bocas_de_subte_curado.csv"
    df_subte_out.to_csv(p_subte, index=False, encoding="utf-8")
    summary["bocas_de_subte_curado.csv"] = {"rows": int(len(df_subte_out)), "cols": int(df_subte_out.shape[1])}

    return summary

