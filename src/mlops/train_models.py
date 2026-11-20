"""Fase 3 (Producto 2): Clustering K-Means, Regresión XGBoost (K-Fold + Tuning), SHAP y exportación .joblib."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".matplotlib_cache"))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
    root_mean_squared_error,
    silhouette_score,
)
from sklearn.model_selection import KFold, RandomizedSearchCV, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from config import settings as config
from mlops import inference

CLUSTER_FEATURES = [
    "ruido_db_promedio",
    "densidad_delitos_500m",
    "distancia_escuela_m",
    "lineas_subte_600m",
    "score_amenities",
]


def _assign_cluster_labels(centroids_df: pd.DataFrame) -> dict[int, str]:
    """Asigna nombres de habitabilidad interpretables a cada clúster según sus centroides."""
    labels: dict[int, str] = {}
    used: set[int] = set()

    # 1. Clúster más ruidoso y de mayor densidad delictiva
    noisy_id = int(
        (centroids_df["ruido_db_promedio"].rank() + centroids_df["densidad_delitos_500m"].rank()).idxmax()
    )
    labels[noisy_id] = "Zona Ruidosa/Alta Densidad"
    used.add(noisy_id)

    # 2. Clúster más tranquilo, seguro y apto para familias (menor ruido + menor delito + cercanía escolar)
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

    # 3. Hub ejecutivo / premium con mayor conectividad y amenities
    rem = centroids_df.drop(index=list(used))
    if not rem.empty:
        hub_id = int((rem["score_amenities"].rank() + rem["lineas_subte_600m"].rank()).idxmax())
        labels[hub_id] = "Hub Ejecutivo Conectado"
        used.add(hub_id)

    # 4. Resto de clústeres intermedios según conectividad de subte vs periferia residencial
    rem = centroids_df.drop(index=list(used))
    for cid in rem.index:
        cid_int = int(cid)
        if rem.loc[cid, "lineas_subte_600m"] >= 1.0:
            labels[cid_int] = "Zona Urbana Conectada"
        else:
            labels[cid_int] = "Zona Residencial Equilibrada"
    return labels


def train_kmeans_segmentation(
    df: pd.DataFrame,
    figures_dir: Path,
) -> tuple[Pipeline, dict[int, str], dict[str, Any]]:
    """Evalúa k=2..6 por Codo y Silhouette, entrena K-Means óptimo y perfila cada clúster."""
    X_clu = df[CLUSTER_FEATURES].astype(float)
    X_scaled = StandardScaler().fit_transform(X_clu)

    k_candidates = [2, 3, 4, 5, 6]
    eval_rows = []
    for k in k_candidates:
        km = KMeans(n_clusters=k, random_state=42, n_init=25)
        preds = km.fit_predict(X_scaled)
        eval_rows.append(
            {
                "k": k,
                "inertia": round(float(km.inertia_), 2),
                "silhouette": round(float(silhouette_score(X_scaled, preds)), 4),
            }
        )
    eval_df = pd.DataFrame(eval_rows)

    # Elegir k >= 3 con mayor Silhouette Score para segmentar en >= 3 perfiles accionables
    sub_ge3 = eval_df[eval_df["k"] >= 3]
    best_k = int(sub_ge3.loc[sub_ge3["silhouette"].idxmax(), "k"])

    kmeans_pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("kmeans", KMeans(n_clusters=best_k, random_state=42, n_init=30)),
        ]
    )
    cluster_ids = kmeans_pipe.fit_predict(X_clu)

    df_tmp = df.copy()
    df_tmp["cluster_id"] = cluster_ids
    centroids = df_tmp.groupby("cluster_id")[CLUSTER_FEATURES].median()
    cluster_labels = _assign_cluster_labels(centroids)
    df_tmp["cluster_label"] = df_tmp["cluster_id"].map(cluster_labels)

    # Perfilado estadístico de cada clúster
    profiles = {}
    for cid, label in cluster_labels.items():
        sub = df_tmp[df_tmp["cluster_id"] == cid]
        profiles[label] = {
            "cluster_id": int(cid),
            "count": int(len(sub)),
            "pct_oferta": round(float(len(sub) / len(df_tmp) * 100.0), 2),
            "median_costo_total_ars": round(float(sub["costo_total_ars"].median()), 2),
            "median_ruido_db": round(float(sub["ruido_db_promedio"].median()), 2),
            "median_delitos_500m": round(float(sub["densidad_delitos_500m"].median()), 2),
            "median_dist_escuela_m": round(float(sub["distancia_escuela_m"].median()), 2),
            "median_lineas_subte_600m": round(float(sub["lineas_subte_600m"].median()), 2),
            "median_score_amenities": round(float(sub["score_amenities"].median()), 2),
        }

    # Test Kruskal-Wallis sobre costo_total_ars entre clústeres finales
    groups = [df_tmp.loc[df_tmp["cluster_id"] == cid, "costo_total_ars"].to_numpy() for cid in sorted(cluster_labels)]
    kw_h, kw_p = stats.kruskal(*groups)

    # Gráfico Codo + Silhouette
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].plot(eval_df["k"], eval_df["inertia"], marker="o", color="#1f77b4")
    axes[0].axvline(best_k, color="#d62728", linestyle="--", label=f"k óptimo = {best_k}")
    axes[0].set_title("Método del Codo (Inercia)")
    axes[0].set_xlabel("Número de clústeres (k)")
    axes[0].set_ylabel("Inercia")
    axes[0].legend()

    axes[1].plot(eval_df["k"], eval_df["silhouette"], marker="s", color="#2ca02c")
    axes[1].axvline(best_k, color="#d62728", linestyle="--", label=f"k óptimo = {best_k}")
    axes[1].set_title("Silhouette Score por k")
    axes[1].set_xlabel("Número de clústeres (k)")
    axes[1].set_ylabel("Silhouette Score")
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(figures_dir / "01_kmeans_elbow_silhouette.png", dpi=140)
    plt.close(fig)

    report = {
        "features": CLUSTER_FEATURES,
        "k_evaluation": eval_rows,
        "optimal_k": best_k,
        "optimal_silhouette": float(eval_df.loc[eval_df["k"] == best_k, "silhouette"].iloc[0]),
        "cluster_labels": cluster_labels,
        "cluster_profiles": profiles,
        "kruskal_costo_total_H": round(float(kw_h), 4),
        "kruskal_costo_total_p": float(kw_p),
    }
    return kmeans_pipe, cluster_labels, report


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "MAE_ars": round(float(mean_absolute_error(y_true, y_pred)), 2),
        "RMSE_ars": round(float(root_mean_squared_error(y_true, y_pred)), 2),
        "MAPE_pct": round(float(mean_absolute_percentage_error(y_true, y_pred) * 100.0), 2),
        "R2": round(float(r2_score(y_true, y_pred)), 4),
    }


def train_xgboost_regressor(
    df_curated: pd.DataFrame,
    figures_dir: Path,
) -> tuple[TransformedTargetRegressor, dict[str, Any]]:
    """Entrena XGBoost con TransformedTargetRegressor(log1p), K-Fold CV, tuning y SHAP."""
    reg_features = [c for c in df_curated.columns if c != config.TARGET_COL]
    X = df_curated[reg_features].astype(float)
    y = df_curated[config.TARGET_COL].astype(float)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    base_model = TransformedTargetRegressor(
        regressor=XGBRegressor(
            objective="reg:squarederror",
            random_state=42,
            n_jobs=-1,
        ),
        func=np.log1p,
        inverse_func=np.expm1,
    )

    param_dist = {
        "regressor__n_estimators": [200, 350, 500, 700],
        "regressor__max_depth": [3, 4, 5, 6],
        "regressor__learning_rate": [0.02, 0.04, 0.06, 0.1],
        "regressor__subsample": [0.75, 0.85, 0.95, 1.0],
        "regressor__colsample_bytree": [0.7, 0.85, 1.0],
        "regressor__min_child_weight": [1, 3, 5],
        "regressor__reg_alpha": [0.0, 0.1, 1.0],
        "regressor__reg_lambda": [1.0, 2.0, 5.0],
    }

    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_dist,
        n_iter=30,
        scoring="neg_root_mean_squared_error",
        cv=cv,
        random_state=42,
        n_jobs=-1,
        refit=True,
    )
    search.fit(X_train, y_train)
    best_model = search.best_estimator_

    # Métricas Hold-out Test (20%)
    y_test_pred = np.clip(best_model.predict(X_test), 1.0, None)
    holdout_metrics = _regression_metrics(y_test.to_numpy(), y_test_pred)

    # Métricas K-Fold Cross-Validation Out-of-Fold sobre el dataset completo
    oof_preds = np.clip(cross_val_predict(best_model, X, y, cv=cv, n_jobs=-1), 1.0, None)
    cv_oof_metrics = _regression_metrics(y.to_numpy(), oof_preds)

    # Entrenar modelo final sobre 100% de los datos curados para artefacto de producción
    final_model = TransformedTargetRegressor(
        regressor=XGBRegressor(**best_model.regressor_.get_params()),
        func=np.log1p,
        inverse_func=np.expm1,
    )
    final_model.fit(X, y)

    # Gráfico Predicho vs Real (Hold-out Test)
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.scatter(y_test / 1e6, y_test_pred / 1e6, alpha=0.65, color="#1f77b4", edgecolors="white", linewidth=0.5)
    lims = [min((y_test / 1e6).min(), (y_test_pred / 1e6).min()), max((y_test / 1e6).max(), (y_test_pred / 1e6).max())]
    ax.plot(lims, lims, "r--", linewidth=1.5, label="Ideal (y = ŷ)")
    ax.set_title(f"XGBoost Hold-out Test: Real vs. Precio Justo\nR² = {holdout_metrics['R2']:.3f} | MAPE = {holdout_metrics['MAPE_pct']:.2f}%")
    ax.set_xlabel("Costo Total Real (Millones ARS)")
    ax.set_ylabel("Precio Justo Predicho (Millones ARS)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "02_xgboost_pred_vs_real.png", dpi=140)
    plt.close(fig)

    # Explicabilidad SHAP (compatible con XGBoost 3.2+ usando Explainer sobre predictor en escala log1p)
    bg = shap.sample(X, min(150, len(X)), random_state=42)
    explainer = shap.Explainer(final_model.regressor_.predict, bg)
    shap_exp = explainer(X)
    shap_values = shap_exp.values

    plt.figure(figsize=(9, 5.5))
    shap.summary_plot(shap_values, X, show=False)
    plt.title("SHAP Summary (Impacto en log1p(Costo Total ARS))")
    plt.tight_layout()
    plt.savefig(figures_dir / "03_shap_summary_beeswarm.png", dpi=140, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(8.5, 5))
    shap.summary_plot(shap_values, X, plot_type="bar", show=False)
    plt.title("SHAP Feature Importance Global (Mean |SHAP value|)")
    plt.tight_layout()
    plt.savefig(figures_dir / "04_shap_feature_importance_bar.png", dpi=140, bbox_inches="tight")
    plt.close()

    mean_abs_shap = {
        feat: round(float(val), 4)
        for feat, val in sorted(
            zip(reg_features, np.abs(shap_values).mean(axis=0)),
            key=lambda kv: kv[1],
            reverse=True,
        )
    }

    report = {
        "features": reg_features,
        "target": config.TARGET_COL,
        "target_transform": "log1p / expm1",
        "best_params": {k.replace("regressor__", ""): v for k, v in search.best_params_.items()},
        "holdout_test_20pct": holdout_metrics,
        "kfold_5_oof_full": cv_oof_metrics,
        "mean_abs_shap_importance": mean_abs_shap,
    }
    return final_model, report


def run_phase3(
    bump: bool = False,
    registry_path: Path | None = None,
    min_r2: float = 0.80,
) -> dict[str, Any]:
    """Ejecuta el entrenamiento completo de Fase 3, exporta .joblib y genera inferencia de muestra."""
    config.PRODUCTO2_DIR.mkdir(parents=True, exist_ok=True)
    config.PRODUCTO2_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    config.PRODUCTO2_FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    df_curated = pd.read_csv(config.OUTPUT_CURATED_CSV)
    df_enriched = pd.read_csv(config.OUTPUT_ENRICHED_CSV)

    kmeans_pipe, cluster_labels, kmeans_report = train_kmeans_segmentation(
        df_curated,
        figures_dir=config.PRODUCTO2_FIGURES_DIR,
    )
    xgb_model, xgb_report = train_xgboost_regressor(
        df_curated,
        figures_dir=config.PRODUCTO2_FIGURES_DIR,
    )

    # Exportar artefactos .joblib base
    metadata = {
        "regression_features": xgb_report["features"],
        "cluster_features": CLUSTER_FEATURES,
        "cluster_labels": cluster_labels,
        "target_col": config.TARGET_COL,
    }
    joblib.dump(kmeans_pipe, config.PRODUCTO2_ARTIFACTS_DIR / "kmeans_model.joblib")
    joblib.dump(xgb_model, config.PRODUCTO2_ARTIFACTS_DIR / "xgb_price_model.joblib")
    joblib.dump(metadata, config.PRODUCTO2_ARTIFACTS_DIR / "model_metadata.joblib")

    # Limpiar caché de inference y correr inferencia batch para ambos perfiles
    inference.load_artifacts.cache_clear()
    res_fam = inference.predict_batch(df_enriched, profile="FAMILIA", published_price_col="costo_total_ars")
    res_sol = inference.predict_batch(df_enriched, profile="SOLTERO_EJECUTIVO", published_price_col="costo_total_ars")

    combined = df_enriched[["listing_id", "barrio", "subzona", "m2_totales", "ambientes", "apto_mascotas", "score_amenities", "costo_total_ars"]].copy()
    combined["cluster_id"] = res_fam["cluster_id"]
    combined["cluster_label"] = res_fam["cluster_label"]
    combined["precio_justo_ars"] = res_fam["precio_justo_ars"]
    combined["pct_sobreprecio"] = res_fam["pct_sobreprecio"]
    combined["pct_ahorro"] = res_fam["pct_ahorro"]
    combined["score_familia"] = res_fam["decision_score_0_100"]
    combined["recomendacion_familia"] = res_fam["recomendacion"]
    combined["score_soltero_ejecutivo"] = res_sol["decision_score_0_100"]
    combined["recomendacion_soltero_ejecutivo"] = res_sol["recomendacion"]

    out_infer_csv = config.PRODUCTO2_DIR / "resultados_inferencia_caba.csv"
    combined.to_csv(out_infer_csv, index=False, encoding="utf-8")

    metrics_report = {
        "kmeans_clustering": kmeans_report,
        "xgboost_regression": xgb_report,
        "inference_summary": {
            "total_properties_scored": int(len(combined)),
            "oportunidades_ahorro_gt_10pct": int((combined["pct_ahorro"] >= 10.0).sum()),
            "sobreprecio_gt_10pct": int((combined["pct_sobreprecio"] >= 10.0).sum()),
            "mean_score_familia": round(float(combined["score_familia"].mean()), 2),
            "mean_score_soltero_ejecutivo": round(float(combined["score_soltero_ejecutivo"].mean()), 2),
        },
        "artifacts": {
            "kmeans_model": str(config.PRODUCTO2_ARTIFACTS_DIR / "kmeans_model.joblib"),
            "xgb_price_model": str(config.PRODUCTO2_ARTIFACTS_DIR / "xgb_price_model.joblib"),
            "model_metadata": str(config.PRODUCTO2_ARTIFACTS_DIR / "model_metadata.joblib"),
            "resultados_inferencia": str(out_infer_csv),
        },
    }

    if bump:
        try:
            from mlops import registry
        except ImportError:
            import registry
        version_rec = registry.bump_version(
            metrics=metrics_report,
            artifacts_src_dir=config.PRODUCTO2_ARTIFACTS_DIR,
            target_artifacts_base=config.PRODUCTO2_ARTIFACTS_DIR,
            registry_path=registry_path,
            min_r2=min_r2,
        )
        metrics_report["registry_version"] = version_rec

    with open(config.PRODUCTO2_DIR / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_report, f, ensure_ascii=False, indent=2)

    return metrics_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entrenamiento y model registry MLOps")
    parser.add_argument("--bump", action="store_true", help="Incrementar versión y archivar en mlops/artifacts/v(N)/")
    parser.add_argument("--registry", type=Path, default=None, help="Ruta personalizada a registry.json")
    parser.add_argument("--min-r2", type=float, default=0.80, help="Umbral mínimo de R2 para aceptar nueva versión")
    args = parser.parse_args()

    rep = run_phase3(bump=args.bump, registry_path=args.registry, min_r2=args.min_r2)
    print("=== FASE 3: K-MEANS CLUSTERING ===")
    print("k óptimo:", rep["kmeans_clustering"]["optimal_k"], "| Silhouette:", rep["kmeans_clustering"]["optimal_silhouette"])
    print("Perfiles:", json.dumps(rep["kmeans_clustering"]["cluster_profiles"], ensure_ascii=False, indent=2))
    print("Kruskal-Wallis costo_total entre clústeres: H=", rep["kmeans_clustering"]["kruskal_costo_total_H"], "p=", rep["kmeans_clustering"]["kruskal_costo_total_p"])
    print("\n=== FASE 3: XGBOOST REGRESSOR ===")
    print("Hold-out Test (20%):", rep["xgboost_regression"]["holdout_test_20pct"])
    print("5-Fold CV OOF (100%):", rep["xgboost_regression"]["kfold_5_oof_full"])
    print("Top SHAP:", rep["xgboost_regression"]["mean_abs_shap_importance"])
    if "registry_version" in rep:
        print("\n=== MLOPS REGISTRY: VERSION BUMP ===")
        print("Nueva versión registrada:", rep["registry_version"]["version"])
    print("\n=== FASE 3: INFERENCIA & SCORE 0-100 ===")
    print(rep["inference_summary"])
