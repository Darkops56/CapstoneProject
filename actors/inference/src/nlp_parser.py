"""Utilidades puras de parsing NLP y limpieza tabular para el Actor de Apify.

Este módulo es 100% autónomo y no depende de ningún módulo fuera del Actor.
"""

import re
from typing import Any
import numpy as np

# Constantes predeterminadas
DEFAULT_TIPO_CAMBIO = 1200.0
DEFAULT_FACTOR_USD = 1.0
DEFAULT_IMPUESTO_SELLOS = 0.005


def _parse_ar_number(raw: str) -> float:
    """Convierte montos con formato argentino ('1.200.000', '172.000', '382000,50') a float."""
    s = raw.strip().rstrip(".,-")
    if not s:
        return np.nan
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


def _extract_first_int(text: str | None) -> float:
    """Extrae el primer entero de una cadena como '95 m² cub.' o '3 amb.'."""
    if not text:
        return np.nan
    m = re.search(r"(\d+)", str(text))
    return float(m.group(1)) if m else np.nan


def parse_price_ars(
    amount: Any,
    currency: str | None,
    tipo_cambio: float = DEFAULT_TIPO_CAMBIO,
    factor_usd: float = DEFAULT_FACTOR_USD,
    sellos: float = DEFAULT_IMPUESTO_SELLOS,
) -> float:
    """Unifica precios en USD o ARS a Pesos Argentinos (ARS) de forma determinista."""
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


def extract_expenses_ars(
    item: dict[str, Any],
    tipo_cambio: float = DEFAULT_TIPO_CAMBIO,
    factor_usd: float = DEFAULT_FACTOR_USD,
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

    if re.search(
        r"\bno\s+(?:se\s+)?(?:acepta\w*|permit\w*|admit\w*)\s+mascotas?\b|\bprohibid\w*\s+mascotas?\b|\bsin\s+mascotas?\b",
        desc,
        re.I,
    ):
        reason = "nlp_negation_override" if struct_yes else "nlp_negation"
        return (0, reason) if return_reason else 0

    if struct_yes:
        return (1, "structured") if return_reason else 1

    if re.search(r"\b(?:apto|acepta\w*|permit\w*|admit\w*)\s+mascotas?\b|\bpet\s*friendly\b", desc, re.I):
        return (1, "nlp_positive") if return_reason else 1

    return (0, "not_specified") if return_reason else 0


def _parse_main_features(item: dict[str, Any]) -> dict[str, float]:
    """Extrae características físicas principales desde mainFeatures (y simplificadas)."""
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


def extract_amenities(item: dict[str, Any]) -> dict[str, float]:
    """Extrae amenities binarios y scores ponderados."""
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
