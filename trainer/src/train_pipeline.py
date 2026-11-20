"""Pipeline de reentrenamiento serverless anual para K-Means y XGBoost."""

import hashlib
import os
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error, silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

CLUSTER_FEATURES = [
    "ruido_db_promedio",
    "densidad_delitos_500m",
    "distancia_escuela_m",
    "lineas_subte_600m",
    "score_amenities",
]

REGRESSION_FEATURES = [
    "m2_totales",
    "ruido_db_promedio",
    "densidad_delitos_500m",
    "distancia_escuela_m",
    "lineas_subte_600m",
    "banos",
    "ambientes",
    "cocheras",
]

DEFAULT_TARGET_COL = "costo_total_ars"
SHAP_BACKGROUND_MAX_SAMPLES = 100


def compute_dataset_hash(df: pd.DataFrame) -> str:
    """Calcula hash SHA-256 determinista del DataFrame de entrenamiento."""
    cols = sorted(list(df.columns))
    csv_bytes = df[cols].to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def compute_shap_background(
    X: pd.DataFrame,
    max_samples: int = SHAP_BACKGROUND_MAX_SAMPLES,
    random_state: int = 42,
) -> pd.DataFrame:
    """Subsamplea el conjunto de fondo para SHAP garantizando ejecución acotada (< 90s)."""
    if len(X) <= max_samples:
        return X.copy()
    return X.sample(n=max_samples, random_state=random_state).reset_index(drop=True)


class InsufficientDataError(ValueError):
    """Excepción canónica cuando el volumen de datos de entrenamiento es menor al mínimo requerido."""

    def __init__(self, message: str = "ERR_INSUFFICIENT_DATA"):
        super().__init__(message)


class MetricRegressionError(ValueError):
    """Excepción canónica cuando las métricas del modelo entrenado no alcanzan el umbral mínimo."""

    def __init__(self, message: str = "ERR_METRIC_REGRESSION"):
        super().__init__(message)


def _assign_cluster_labels(centroids_df: pd.DataFrame) -> dict[int, str]:
    """Asigna nombres de habitabilidad interpretables a cada clúster según sus centroides."""
    labels: dict[int, str] = {}
    used: set[int] = set()

    noisy_id = int((centroids_df["ruido_db_promedio"].rank() + centroids_df["densidad_delitos_500m"].rank()).idxmax())
    labels[noisy_id] = "Zona Ruidosa/Alta Densidad"
    used.add(noisy_id)

    rem = centroids_df.drop(index=list(used))
    if not rem.empty:
        fam_id = int(
            (
                rem["ruido_db_promedio"].rank()
                + rem["densidad_delitos_500m"].rank()
                + 0.5 * rem["distancia_escuela_m"].rank()
            ).idxmin()
        )
        labels[fam_id] = "Zona Familiar Tranquila"
        used.add(fam_id)

    rem = centroids_df.drop(index=list(used))
    if not rem.empty:
        hub_id = int((rem["score_amenities"].rank() + rem["lineas_subte_600m"].rank()).idxmax())
        labels[hub_id] = "Hub Ejecutivo Conectado"
        used.add(hub_id)

    rem = centroids_df.drop(index=list(used))
    for cid in rem.index:
        cid_int = int(cid)
        if rem.loc[cid, "lineas_subte_600m"] >= 1.0:
            labels[cid_int] = "Zona Urbana Conectada"
        else:
            labels[cid_int] = "Zona Residencial Equilibrada"
    return labels


def train_kmeans(df: pd.DataFrame) -> tuple[Pipeline, dict[int, str], dict[str, Any]]:
    """Entrena K-Means óptimo evaluando siluetas y genera pipeline."""
    X = df[CLUSTER_FEATURES].astype(float)
    X_scaled = StandardScaler().fit_transform(X)

    best_k = 5
    best_sil = -1.0
    for k in [2, 3, 4, 5, 6]:
        km_test = KMeans(n_clusters=k, random_state=42, n_init=15)
        preds = km_test.fit_predict(X_scaled)
        sil = float(silhouette_score(X_scaled, preds))
        if sil > best_sil:
            best_sil = sil
            best_k = k

    final_scaler = StandardScaler()
    final_km = KMeans(n_clusters=best_k, random_state=42, n_init=20)
    pipeline_kmeans = Pipeline([("scaler", final_scaler), ("kmeans", final_km)])
    pipeline_kmeans.fit(X)

    centroids = pd.DataFrame(final_scaler.inverse_transform(final_km.cluster_centers_), columns=CLUSTER_FEATURES)
    labels = _assign_cluster_labels(centroids)

    report = {
        "optimal_k": best_k,
        "silhouette_score": round(best_sil, 4),
        "cluster_labels": labels,
    }
    return pipeline_kmeans, labels, report


def train_xgboost(
    df: pd.DataFrame,
    target_col: str = DEFAULT_TARGET_COL,
    min_r2: float = 0.80,
) -> tuple[TransformedTargetRegressor, dict[str, Any]]:
    """Entrena XGBRegressor con log1p transform y valida umbrales de métricas."""
    X = df[REGRESSION_FEATURES].copy().fillna(0)
    y = df[target_col].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    base_reg = XGBRegressor(
        n_estimators=250,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )

    ttr = TransformedTargetRegressor(regressor=base_reg, func=np.log1p, inverse_func=np.expm1)
    ttr.fit(X_train, y_train)

    y_pred = ttr.predict(X_test)
    r2_val = float(r2_score(y_test, y_pred))
    rmse_val = float(root_mean_squared_error(y_test, y_pred))
    mae_val = float(mean_absolute_error(y_test, y_pred))

    report = {
        "r2": round(r2_val, 4),
        "rmse": round(rmse_val, 2),
        "mae": round(mae_val, 2),
        "features": REGRESSION_FEATURES,
        "target": target_col,
    }

    if r2_val < min_r2:
        raise MetricRegressionError(
            f"ERR_METRIC_REGRESSION: El modelo obtuvo R2 = {r2_val:.4f}, inferior al umbral requerido de {min_r2:.4f}"
        )

    return ttr, report


def run_training_pipeline(
    df: pd.DataFrame,
    output_dir: Path,
    min_samples: int = 500,
    min_r2: float = 0.80,
    target_col: str = DEFAULT_TARGET_COL,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo de entrenamiento y exporta artefactos locales."""
    if len(df) < min_samples:
        raise InsufficientDataError(
            f"ERR_INSUFFICIENT_DATA: Se requieren al menos {min_samples} registros para entrenar, recibidos: {len(df)}"
        )

    # Validar columnas requeridas
    missing_clu = set(CLUSTER_FEATURES) - set(df.columns)
    if missing_clu:
        raise ValueError(f"Faltan columnas de clúster en el dataset: {missing_clu}")

    missing_reg = (set(REGRESSION_FEATURES) | {target_col}) - set(df.columns)
    if missing_reg:
        raise ValueError(f"Faltan columnas de regresión en el dataset: {missing_reg}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. K-Means
    kmeans_pipe, cluster_labels, kmeans_report = train_kmeans(df)

    # 2. XGBoost + subsampling de fondo SHAP (N <= 100)
    xgb_model, xgb_report = train_xgboost(df, target_col=target_col, min_r2=min_r2)
    shap_bg = compute_shap_background(df[REGRESSION_FEATURES].fillna(0))
    dataset_hash = compute_dataset_hash(df)

    # 3. Metadatos
    metadata = {
        "regression_features": REGRESSION_FEATURES,
        "cluster_features": CLUSTER_FEATURES,
        "cluster_labels": cluster_labels,
        "target_col": target_col,
        "dataset_hash": dataset_hash,
        "shap_background_size": len(shap_bg),
        "metrics": {
            "r2": xgb_report["r2"],
            "rmse": xgb_report["rmse"],
            "mae": xgb_report["mae"],
            "silhouette": kmeans_report["silhouette_score"],
        },
    }

    # 4. Guardar archivos .joblib
    kmeans_path = output_dir / "kmeans_model.joblib"
    xgb_path = output_dir / "xgb_price_model.joblib"
    meta_path = output_dir / "model_metadata.joblib"

    joblib.dump(kmeans_pipe, kmeans_path)
    joblib.dump(xgb_model, xgb_path)
    joblib.dump(metadata, meta_path)

    return {
        "status": "success",
        "sample_count": len(df),
        "dataset_hash": dataset_hash,
        "shap_background_size": len(shap_bg),
        "kmeans_report": kmeans_report,
        "xgboost_report": xgb_report,
        "artifacts": {
            "kmeans_model": str(kmeans_path),
            "xgb_price_model": str(xgb_path),
            "model_metadata": str(meta_path),
        },
        "metrics": metadata["metrics"],
    }
