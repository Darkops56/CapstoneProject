"""Helpers defensivos y testeables para el Notebook Maestro End-to-End (CABA).

Encapsula las fronteras externas (creación dinámica de carpetas, descarga desde
CKAN GCBA, ingesta desde el actor scraper `memo23~zonaprop-scraper` de Apify) y
las rutinas de evaluación comparativa (Baseline vs. Modelos y auditoría de error
por subgrupo) con discriminadores causales 1:1.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

# Tokens canónicos de error (Principio de No-Colapso Semántico)
ERR_MISSING_APIFY_TOKEN = "ERR_MISSING_APIFY_TOKEN"
ERR_INVALID_APIFY_MODE = "ERR_INVALID_APIFY_MODE"
ERR_GCBA_DOWNLOAD = "ERR_GCBA_DOWNLOAD"
ERR_GCBA_SCHEMA = "ERR_GCBA_SCHEMA"
ERR_APIFY_SCRAPER_FAILED = "ERR_APIFY_SCRAPER_FAILED"
ERR_METRIC_REGRESSION = "ERR_METRIC_REGRESSION"

# Configuración alineada con workflows/n8n/Pipeline Completo Anual y Mensual.json
CKAN_API_BASE = "https://data.buenosaires.gob.ar/api/3/action/package_show"
APIFY_API_BASE = "https://api.apify.com/v2"
APIFY_SCRAPER_ACTOR_ID = "memo23~zonaprop-scraper"
ZONAPROP_START_URL = "https://www.zonaprop.com.ar/departamentos-alquiler-capital-federal.html"

HTTP_TIMEOUT_S = 60
APIFY_WAIT_FOR_FINISH_S = 300

# Catálogo oficial GCBA con filtros semánticos y columnas mínimas aceptadas
CKAN_CATALOG: list[dict[str, Any]] = [
    {
        "dataset_id": "delitos",
        "target_stem": "delitos_2022",
        "preferred_keywords": ["2023", "2022", "delitos"],
        "required_any_cols": ["latitud", "lat", "longitud", "long", "tipo", "tipo_delito"],
    },
    {
        "dataset_id": "bocas-subte",
        "target_stem": "bocas-de-subte",
        "preferred_keywords": ["bocas", "subte"],
        "required_any_cols": ["lat", "long", "linea", "estacion", "wkt"],
    },
    {
        "dataset_id": "mapa-ruido",
        "target_stem": "medicion_de_ruido_diurno_2018",
        "preferred_keywords": ["diurno", "ruido"],
        "required_any_cols": ["wkt", "geometry", "rango", "rango_db", "decibeles", "lat", "long"],
    },
    {
        "dataset_id": "establecimientos-educativos",
        "target_stem": "establecimientos_educativos",
        "preferred_keywords": ["establecimientos", "educativos"],
        "required_any_cols": ["lat", "long", "x", "y", "wkt", "nombre", "fna", "dom_edific"],
    },
]


class NotebookPipelineError(RuntimeError):
    """Excepción de frontera con discriminador causal 1:1 (tipo, razon)."""

    def __init__(self, tipo: str, razon: str, detail: str = "") -> None:
        self.tipo = tipo
        self.razon = razon
        self.detail = detail
        msg = f"[{tipo}] {razon}" + (f": {detail}" if detail else "")
        super().__init__(msg)

    def to_dict(self) -> dict[str, str]:
        return {"tipo": self.tipo, "razon": self.razon, "detail": self.detail}


def ensure_runtime_dirs(base_dir: Path | str) -> dict[str, Path]:
    """Crea dinámicamente las carpetas de trabajo del pipeline en runtime."""
    root = Path(base_dir)
    dirs = {
        "datasets_originales": root / "Datasets" / "Originales",
        "datasets_curados": root / "Datasets" / "Curados",
        "etl_output": root / "etl" / "output",
        "mlops_artifacts": root / "mlops" / "artifacts",
        "mlops_figures": root / "mlops" / "figures",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def select_ckan_resource(
    resources: list[dict[str, Any]],
    preferred_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Selecciona de forma defensiva el mejor recurso tabular (CSV/XLSX) de CKAN."""
    keywords = [k.lower() for k in (preferred_keywords or [])]
    tabular: list[tuple[int, dict[str, Any]]] = []

    for res in resources or []:
        url = str(res.get("url") or "").strip()
        if not url:
            continue
        fmt = str(res.get("format") or "").strip().lower()
        name = str(res.get("name") or "").strip().lower()
        url_low = url.lower()

        is_csv = fmt == "csv" or url_low.endswith(".csv")
        is_xlsx = fmt in {"xlsx", "xls"} or url_low.endswith((".xlsx", ".xls"))
        if not (is_csv or is_xlsx):
            continue

        score = 10 if is_csv else 8
        for idx, kw in enumerate(keywords):
            if kw in name or kw in url_low:
                score += max(1, 5 - idx)
        tabular.append((score, res))

    if not tabular:
        raise NotebookPipelineError(
            tipo="FAILED",
            razon=ERR_GCBA_DOWNLOAD,
            detail="El paquete CKAN no contiene recursos CSV o XLSX descargables.",
        )

    tabular.sort(key=lambda item: item[0], reverse=True)
    return tabular[0][1]


def _validate_tabular_bytes(
    raw_bytes: bytes,
    ext: str,
    required_any_cols: list[str],
    dataset_id: str,
) -> list[str]:
    """Valida que los bytes descargados sean legibles y contengan columnas esperadas."""
    try:
        if ext == ".csv":
            # Detecta separador común (, o ;) sin fallar por BOM
            sample = raw_bytes[:4096].decode("utf-8", errors="ignore")
            sep = ";" if sample.count(";") > sample.count(",") else ","
            df_head = pd.read_csv(io.BytesIO(raw_bytes), sep=sep, nrows=5)
        else:
            df_head = pd.read_excel(io.BytesIO(raw_bytes), nrows=5)
    except Exception as exc:
        raise NotebookPipelineError(
            tipo="FAILED",
            razon=ERR_GCBA_SCHEMA,
            detail=f"No se pudo parsear {dataset_id} ({ext}): {exc}",
        ) from exc

    cols_norm = [str(c).strip().lower() for c in df_head.columns]
    req_norm = [c.strip().lower() for c in required_any_cols]
    if not any(col in cols_norm for col in req_norm):
        raise NotebookPipelineError(
            tipo="FAILED",
            razon=ERR_GCBA_SCHEMA,
            detail=(
                f"Dataset '{dataset_id}' sin columnas esperadas. "
                f"Esperaba al menos una de {req_norm}, recibió {cols_norm}."
            ),
        )
    return cols_norm


def download_gcba_datasets(
    dest_dir: Path | str,
    catalog: list[dict[str, Any]] | None = None,
    skip_if_exists: bool = True,
    timeout_s: int = HTTP_TIMEOUT_S,
) -> dict[str, dict[str, Any]]:
    """Descarga y valida los 4 datasets oficiales de GCBA desde la CKAN API."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    entries = catalog if catalog is not None else CKAN_CATALOG
    report: dict[str, dict[str, Any]] = {}

    for entry in entries:
        dataset_id = entry["dataset_id"]
        stem = entry["target_stem"]

        # Reutilización opcional si ya existe localmente en la sesión
        if skip_if_exists:
            existing = next(
                (p for p in (dest / f"{stem}.csv", dest / f"{stem}.xlsx") if p.exists() and p.stat().st_size > 0),
                None,
            )
            if existing is not None:
                report[dataset_id] = {
                    "tipo": "OK",
                    "razon": "CACHED_LOCAL",
                    "path": str(existing),
                }
                continue

        try:
            meta_resp = requests.get(
                f"{CKAN_API_BASE}?id={dataset_id}",
                timeout=timeout_s,
            )
            if getattr(meta_resp, "status_code", 500) >= 400:
                raise RuntimeError(f"HTTP {meta_resp.status_code}")
            meta_resp.raise_for_status()
            payload = meta_resp.json()
        except Exception as exc:
            raise NotebookPipelineError(
                tipo="FAILED",
                razon=ERR_GCBA_DOWNLOAD,
                detail=f"Error consultando CKAN para '{dataset_id}': {exc}",
            ) from exc

        resources = (payload.get("result") or {}).get("resources") or []
        chosen = select_ckan_resource(resources, entry.get("preferred_keywords"))
        url = str(chosen["url"])
        fmt = str(chosen.get("format") or "").strip().lower()
        ext = ".xlsx" if (fmt in {"xlsx", "xls"} or url.lower().endswith((".xlsx", ".xls"))) else ".csv"

        try:
            file_resp = requests.get(url, timeout=timeout_s)
            if getattr(file_resp, "status_code", 500) >= 400:
                raise RuntimeError(f"HTTP {file_resp.status_code}")
            file_resp.raise_for_status()
            raw_bytes = file_resp.content
            if not raw_bytes:
                raise RuntimeError("Respuesta vacía al descargar archivo.")
        except Exception as exc:
            raise NotebookPipelineError(
                tipo="FAILED",
                razon=ERR_GCBA_DOWNLOAD,
                detail=f"Error descargando recurso '{url}' para '{dataset_id}': {exc}",
            ) from exc

        # Validación de esquema en memoria antes de persistir a disco (escritura atómica)
        cols_found = _validate_tabular_bytes(
            raw_bytes=raw_bytes,
            ext=ext,
            required_any_cols=entry.get("required_any_cols", []),
            dataset_id=dataset_id,
        )

        out_path = dest / f"{stem}{ext}"
        out_path.write_bytes(raw_bytes)
        report[dataset_id] = {
            "tipo": "OK",
            "razon": "COMPLETED",
            "path": str(out_path),
            "url": url,
            "columns_sample": cols_found[:10],
        }

    return report


def fetch_zonaprop_apify(
    token: str | None,
    output_path: Path | str,
    mode: str = "last_run",
    max_items: int = 200,
    actor_id: str = APIFY_SCRAPER_ACTOR_ID,
    wait_for_finish_s: int = APIFY_WAIT_FOR_FINISH_S,
) -> dict[str, Any]:
    """Obtiene avisos crudos de Zonaprop exclusivamente vía el scraper de Apify."""
    clean_token = (token or "").strip()
    if not clean_token:
        raise NotebookPipelineError(
            tipo="ABORTED",
            razon=ERR_MISSING_APIFY_TOKEN,
            detail="Configurá la variable de entorno APIFY_TOKEN antes de ejecutar la ingesta.",
        )

    if mode not in {"last_run", "run_new"}:
        raise NotebookPipelineError(
            tipo="ABORTED",
            razon=ERR_INVALID_APIFY_MODE,
            detail=f"Modo '{mode}' inválido. Valores soportados: 'last_run' o 'run_new'.",
        )

    headers = {"Authorization": f"Bearer {clean_token}", "Content-Type": "application/json"}

    try:
        if mode == "last_run":
            runs_url = f"{APIFY_API_BASE}/acts/{actor_id}/runs?limit=20&desc=true"
            runs_resp = requests.get(runs_url, headers=headers, timeout=HTTP_TIMEOUT_S)
            if getattr(runs_resp, "status_code", 500) >= 400:
                raise RuntimeError(f"HTTP {runs_resp.status_code} listando runs")
            runs_items = ((runs_resp.json() or {}).get("data") or {}).get("items") or []
            succeeded = [r for r in runs_items if r.get("status") == "SUCCEEDED" and r.get("defaultDatasetId")]
            if not succeeded:
                raise RuntimeError("No se encontró ningún run SUCCEEDED previo. Probá con APIFY_MODE='run_new'.")
            dataset_id = succeeded[0]["defaultDatasetId"]
        else:
            run_url = f"{APIFY_API_BASE}/acts/{actor_id}/runs?waitForFinish={int(wait_for_finish_s)}"
            body = {
                "maxItems": int(max_items),
                "startUrls": [{"url": ZONAPROP_START_URL}],
            }
            run_resp = requests.post(run_url, headers=headers, json=body, timeout=int(wait_for_finish_s) + 30)
            if getattr(run_resp, "status_code", 500) >= 400:
                raise RuntimeError(f"HTTP {run_resp.status_code} disparando run_new")
            run_data = (run_resp.json() or {}).get("data") or {}
            if run_data.get("status") != "SUCCEEDED" or not run_data.get("defaultDatasetId"):
                raise RuntimeError(f"Run terminó con estado={run_data.get('status')}")
            dataset_id = run_data["defaultDatasetId"]

        ds_url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items?clean=true"
        items_resp = requests.get(ds_url, headers=headers, timeout=HTTP_TIMEOUT_S)
        if getattr(items_resp, "status_code", 500) >= 400:
            raise RuntimeError(f"HTTP {items_resp.status_code} descargando dataset {dataset_id}")
        items = items_resp.json()
        if not isinstance(items, list) or len(items) < 1:
            raise RuntimeError("El dataset devuelto por el scraper está vacío (0 ítems).")
    except NotebookPipelineError:
        raise
    except Exception as exc:
        raise NotebookPipelineError(
            tipo="FAILED",
            razon=ERR_APIFY_SCRAPER_FAILED,
            detail=f"Fallo en scraper '{actor_id}' (mode={mode}): {exc}",
        ) from exc

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "tipo": "OK",
        "razon": "COMPLETED",
        "mode": mode,
        "dataset_id": dataset_id,
        "count": len(items),
        "path": str(out),
    }


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true_arr = np.asarray(y_true, dtype=float)
    y_pred_arr = np.asarray(y_pred, dtype=float)
    mae = float(mean_absolute_error(y_true_arr, y_pred_arr))
    rmse = float(np.sqrt(mean_squared_error(y_true_arr, y_pred_arr)))
    mape = float(np.mean(np.abs((y_true_arr - y_pred_arr) / np.clip(y_true_arr, 1e-6, None))) * 100.0)
    r2 = float(r2_score(y_true_arr, y_pred_arr))
    return {"MAE_ars": mae, "RMSE_ars": rmse, "MAPE_pct": mape, "R2": r2}


def evaluate_baseline_vs_models(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str = "costo_total_ars",
    min_r2_threshold: float = 0.50,
    random_state: int = 42,
) -> dict[str, Any]:
    """Evalúa DummyRegressor, Ridge, RandomForest y XGBoost sin data leakage."""
    X = df[feature_cols].astype(float)
    y = df[target_col].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state
    )

    # Todos los modelos se encapsulan en Pipeline + TransformedTargetRegressor(log1p)
    # para que imputación y escalado aprendan exclusivamente en X_train (cero leakage).
    candidates = [
        ("DummyRegressor", DummyRegressor(strategy="median")),
        ("Ridge", Ridge(alpha=10.0)),
        (
            "RandomForestRegressor",
            RandomForestRegressor(n_estimators=150, max_depth=8, random_state=random_state, n_jobs=-1),
        ),
        (
            "XGBoost",
            XGBRegressor(
                n_estimators=200,
                max_depth=3,
                learning_rate=0.06,
                subsample=0.75,
                min_child_weight=5,
                reg_lambda=1.0,
                random_state=random_state,
                n_jobs=-1,
            ),
        ),
    ]

    rows: list[dict[str, Any]] = []
    fitted_models: dict[str, Any] = {}
    predictions: dict[str, np.ndarray] = {}

    for name, estimator in candidates:
        pipe = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", estimator),
            ]
        )
        ttr = TransformedTargetRegressor(
            regressor=pipe, func=np.log1p, inverse_func=np.expm1
        )
        ttr.fit(X_train, y_train)
        y_pred = np.clip(ttr.predict(X_test), 0.0, None)
        metrics = _regression_metrics(y_test.to_numpy(), y_pred)
        rows.append({"model": name, **metrics})
        fitted_models[name] = ttr
        predictions[name] = y_pred

    comparison_df = pd.DataFrame(rows)
    xgb_r2 = float(comparison_df.loc[comparison_df["model"] == "XGBoost", "R2"].iloc[0])
    dummy_r2 = float(comparison_df.loc[comparison_df["model"] == "DummyRegressor", "R2"].iloc[0])

    if xgb_r2 <= dummy_r2 or xgb_r2 < min_r2_threshold:
        raise NotebookPipelineError(
            tipo="REJECTED",
            razon=ERR_METRIC_REGRESSION,
            detail=(
                f"XGBoost R2={xgb_r2:.4f} no cumple guardrail "
                f"(Dummy R2={dummy_r2:.4f}, umbral mínimo={min_r2_threshold:.2f})."
            ),
        )

    return {
        "comparison_df": comparison_df,
        "fitted_models": fitted_models,
        "X_train": X_train,
        "X_test": X_test,
        "y_train": y_train,
        "y_test": y_test,
        "xgb_predictions": predictions["XGBoost"],
    }


def compute_subgroup_error_audit(
    df_eval: pd.DataFrame,
    y_true_col: str = "costo_total_ars",
    y_pred_col: str = "precio_predicho_ars",
    barrio_col: str = "barrio",
    min_barrio_count: int = 3,
) -> dict[str, pd.DataFrame]:
    """Audita MAE y MAPE por barrio y por cuartil de precio ('¿a quién le falla el modelo?')."""
    work = df_eval[[y_true_col, y_pred_col]].copy()
    if barrio_col in df_eval.columns:
        work[barrio_col] = df_eval[barrio_col].fillna("Sin Barrio").astype(str)
    else:
        work[barrio_col] = "CABA"

    work["abs_err"] = (work[y_true_col] - work[y_pred_col]).abs()
    work["ape_pct"] = (work["abs_err"] / np.clip(work[y_true_col].astype(float), 1e-6, None)) * 100.0

    by_barrio = (
        work.groupby(barrio_col, observed=False)
        .agg(
            count=(y_true_col, "size"),
            MAE_ars=("abs_err", "mean"),
            MAPE_pct=("ape_pct", "mean"),
        )
        .reset_index()
    )
    by_barrio = by_barrio[by_barrio["count"] >= min_barrio_count].sort_values(
        "MAPE_pct", ascending=False
    )

    work["cuartil_precio"] = pd.qcut(
        work[y_true_col],
        q=4,
        labels=["Q1 (Económico)", "Q2 (Medio-Bajo)", "Q3 (Medio-Alto)", "Q4 (Premium)"],
        duplicates="drop",
    )
    by_quartile = (
        work.groupby("cuartil_precio", observed=False)
        .agg(
            count=(y_true_col, "size"),
            MAE_ars=("abs_err", "mean"),
            MAPE_pct=("ape_pct", "mean"),
        )
        .reset_index()
    )

    return {"by_barrio": by_barrio, "by_quartile": by_quartile}
