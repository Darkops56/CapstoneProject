"""Fase 1 y Fase 2: Auditoría ETL, EDA estadístico profundo y selección de 10 features (Producto 1)."""

import json
import os
from pathlib import Path
from typing import Any

# Evitar warnings de Matplotlib por permisos en perfil de usuario en Windows
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent.parent / ".matplotlib_cache"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

from config import settings as config
from etl import etl_pipeline as etl


BUSINESS_QUESTIONS = [
    {
        "id": "Q1",
        "pregunta": "¿Qué zonas y segmentos de departamentos de CABA ofrecen el mejor equilibrio entre calidad ambiental (<65 dBA, baja gravedad delictiva) y conectividad/servicios según el perfil del empleado (FAMILIA vs. SOLTERO_EJECUTIVO)?",
        "objetivo_analitico": "Segmentación K-Means sobre entorno urbano + amenities diferenciados por perfil.",
    },
    {
        "id": "Q2",
        "pregunta": "¿Cuál es el impacto estadísticamente significativo de las externalidades urbanas (ruido diurno >65 dBA, densidad/gravedad delictiva, distancia al subte y oferta escolar) sobre el precio por m² y el costo total mensual?",
        "objetivo_analitico": "Pruebas de hipótesis (Mann-Whitney U, ANOVA/Kruskal-Wallis, Spearman) y explicabilidad.",
    },
    {
        "id": "Q3",
        "pregunta": "¿Qué proporción de la oferta presenta sobreprecio o subvaluación frente al precio justo teórico (alquiler + expensas) explicado por atributos físicos, amenities y entorno?",
        "objetivo_analitico": "Base de métricas de asimetría/dispersión y target limpio costo_total_ars para regresión.",
    },
    {
        "id": "Q4",
        "pregunta": "¿Cómo afectan las inconsistencias de publicación (etiquetas contradictorias sobre mascotas, expensas omitidas y coordenadas fuera de rango) a la elegibilidad real para relocalización corporativa?",
        "objetivo_analitico": "Auditoría ETL con reglas NLP con negaciones, imputación por m²/barrio con banderas y limpieza espacial.",
    },
    {
        "id": "Q5",
        "pregunta": "¿Qué subconjunto de máximo 10 variables ortogonales (VIF controlado) concentra mayor poder predictivo e información mutua para estimar costo_total_ars sin redundancia?",
        "objetivo_analitico": "Selección matemática combinando VIF iterativo + Random Forest + Mutual Information.",
    },
]

# Pool candidato de features (sin variables con leakage directo del target ni IDs)
CANDIDATE_FEATURES = [
    "m2_totales",
    "m2_cubiertos",
    "ambientes",
    "dormitorios",
    "banos",
    "toilettes",
    "cocheras",
    "antiguedad_anios",
    "es_a_estrenar",
    "apto_mascotas",
    "score_amenities",
    "score_amenities_soltero",
    "score_amenities_familia",
    "ruido_db_promedio",
    "densidad_delitos_500m",
    "densidad_robos_500m",
    "indice_gravedad_delitos_500m",
    "escuelas_familias_500m",
    "distancia_escuela_m",
    "distancia_subte_m",
    "lineas_subte_600m",
    "comuna",
]

# Pilares obligatorios solicitados en la especificación
MANDATORY_FEATURES = ["apto_mascotas", "score_amenities"]

# Familias de dominio para asegurar cobertura equilibrada (entorno urbano + físicas + mascotas + amenities)
DOMAIN_GROUPS = {
    "fisicas": ["m2_totales", "m2_cubiertos", "ambientes", "dormitorios", "banos", "toilettes", "cocheras", "antiguedad_anios", "es_a_estrenar"],
    "ruido": ["ruido_db_promedio"],
    "seguridad": ["indice_gravedad_delitos_500m", "densidad_robos_500m", "densidad_delitos_500m"],
    "educacion": ["escuelas_familias_500m", "distancia_escuela_m"],
    "transporte": ["distancia_subte_m", "lineas_subte_600m"],
}


def compute_descriptive_stats(df: pd.DataFrame, cols: list[str]) -> dict[str, dict[str, float]]:
    """Calcula estadísticas descriptivas completas (media, mediana, IQR, asimetría, curtosis, log1p)."""
    res: dict[str, dict[str, float]] = {}
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        iqr = q3 - q1
        skew_val = float(stats.skew(s, bias=False)) if len(s) > 2 else 0.0
        kurt_val = float(stats.kurtosis(s, bias=False)) if len(s) > 3 else 0.0
        skew_log = float(stats.skew(np.log1p(s.clip(lower=0)), bias=False)) if len(s) > 2 and (s >= 0).all() else np.nan

        res[col] = {
            "count": int(len(s)),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std(ddof=1)), 4),
            "min": round(float(s.min()), 4),
            "q25": round(q1, 4),
            "median": round(float(s.median()), 4),
            "q75": round(q3, 4),
            "iqr": round(iqr, 4),
            "max": round(float(s.max()), 4),
            "skewness": round(skew_val, 4),
            "kurtosis": round(kurt_val, 4),
            "skewness_log1p": round(skew_log, 4) if not np.isnan(skew_log) else None,
        }
    return res


def _interpret_p(p: float, alpha: float = 0.05) -> str:
    return "Rechazo H0 (diferencia estadísticamente significativa)" if p < alpha else "No rechazo H0 (sin evidencia significativa)"


def run_hypothesis_tests(df: pd.DataFrame) -> dict[str, Any]:
    """Ejecuta pruebas de normalidad, Mann-Whitney U, Welch t-test, ANOVA, Kruskal-Wallis, Chi2 y Spearman."""
    tests: dict[str, Any] = {}

    # 0. Normalidad (Shapiro-Wilk) sobre precio_m2_total_ars y costo_total_ars
    for col in ["costo_total_ars", "precio_m2_total_ars", "log_precio_m2"]:
        series = np.log1p(df["precio_m2_total_ars"]) if col == "log_precio_m2" else df[col]
        w_stat, p_val = stats.shapiro(series.sample(min(len(series), 500), random_state=42))
        tests[f"normality_shapiro_{col}"] = {
            "W": round(float(w_stat), 4),
            "p_value": float(p_val),
            "normal_alpha_05": bool(p_val >= 0.05),
        }

    # 1. Ruido diurno: > 65 dBA vs <= 65 dBA en precio/m2 y costo total
    noisy = df.loc[df["ruido_db_promedio"] > 65.0, "precio_m2_total_ars"]
    quiet = df.loc[df["ruido_db_promedio"] <= 65.0, "precio_m2_total_ars"]
    u_ruido, p_u_ruido = stats.mannwhitneyu(noisy, quiet, alternative="two-sided")
    t_ruido, p_t_ruido = stats.ttest_ind(noisy, quiet, equal_var=False)
    lev_ruido, p_lev_ruido = stats.levene(noisy, quiet)
    tests["H1_ruido_gt_65_vs_le_65_precio_m2"] = {
        "n_ruidoso_gt_65": int(len(noisy)),
        "n_tranquilo_le_65": int(len(quiet)),
        "median_ruidoso": round(float(noisy.median()), 2),
        "median_tranquilo": round(float(quiet.median()), 2),
        "mean_ruidoso": round(float(noisy.mean()), 2),
        "mean_tranquilo": round(float(quiet.mean()), 2),
        "levene_p": float(p_lev_ruido),
        "mann_whitney_U": float(u_ruido),
        "mann_whitney_p": float(p_u_ruido),
        "welch_t": round(float(t_ruido), 4),
        "welch_p": float(p_t_ruido),
        "decision": _interpret_p(float(p_u_ruido)),
    }

    # 2. Cercanía al subte (<= 600m vs > 600m) en precio/m2
    near_subte = df.loc[df["distancia_subte_m"] <= 600.0, "precio_m2_total_ars"]
    far_subte = df.loc[df["distancia_subte_m"] > 600.0, "precio_m2_total_ars"]
    u_subte, p_u_subte = stats.mannwhitneyu(near_subte, far_subte, alternative="two-sided")
    tests["H2_subte_le_600m_vs_gt_600m_precio_m2"] = {
        "n_cerca_subte": int(len(near_subte)),
        "n_lejos_subte": int(len(far_subte)),
        "median_cerca": round(float(near_subte.median()), 2),
        "median_lejos": round(float(far_subte.median()), 2),
        "mann_whitney_U": float(u_subte),
        "mann_whitney_p": float(p_u_subte),
        "decision": _interpret_p(float(p_u_subte)),
    }

    # 3. Apto mascotas (1 vs 0) en costo total y precio/m2
    pets_yes = df.loc[df["apto_mascotas"] == 1, "precio_m2_total_ars"]
    pets_no = df.loc[df["apto_mascotas"] == 0, "precio_m2_total_ars"]
    u_pets, p_u_pets = stats.mannwhitneyu(pets_yes, pets_no, alternative="two-sided")
    tests["H3_apto_mascotas_precio_m2"] = {
        "n_apto": int(len(pets_yes)),
        "n_no_apto": int(len(pets_no)),
        "median_apto": round(float(pets_yes.median()), 2),
        "median_no_apto": round(float(pets_no.median()), 2),
        "mann_whitney_U": float(u_pets),
        "mann_whitney_p": float(p_u_pets),
        "decision": _interpret_p(float(p_u_pets)),
    }

    # 4. Diferencias entre macro-barrios (con n >= 15) -> ANOVA + Kruskal-Wallis
    barrio_counts = df["barrio"].value_counts()
    top_barrios = barrio_counts[barrio_counts >= 15].index.tolist()
    groups_barrio = [df.loc[df["barrio"] == b, "precio_m2_total_ars"].to_numpy() for b in top_barrios]
    f_bar, p_f_bar = stats.f_oneway(*groups_barrio)
    h_bar, p_h_bar = stats.kruskal(*groups_barrio)
    tests["H4_barrios_precio_m2"] = {
        "barrios_evaluados": top_barrios,
        "medians_por_barrio": {b: round(float(df.loc[df["barrio"] == b, "precio_m2_total_ars"].median()), 2) for b in top_barrios},
        "anova_F": round(float(f_bar), 4),
        "anova_p": float(p_f_bar),
        "kruskal_H": round(float(h_bar), 4),
        "kruskal_p": float(p_h_bar),
        "decision": _interpret_p(float(p_h_bar)),
    }

    # 5. Diferencias entre clústeres urbanos preliminares (KMeans k=3 sobre entorno) -> ANOVA + Kruskal-Wallis
    env_cols = ["ruido_db_promedio", "indice_gravedad_delitos_500m", "distancia_subte_m", "escuelas_familias_500m"]
    env_scaled = StandardScaler().fit_transform(df[env_cols])
    km_prelim = KMeans(n_clusters=3, random_state=42, n_init=20).fit_predict(env_scaled)
    groups_cl = [df.loc[km_prelim == k, "precio_m2_total_ars"].to_numpy() for k in sorted(np.unique(km_prelim))]
    f_cl, p_f_cl = stats.f_oneway(*groups_cl)
    h_cl, p_h_cl = stats.kruskal(*groups_cl)
    tests["H5_clusters_urbanos_preliminares_precio_m2"] = {
        "k": 3,
        "features_entorno": env_cols,
        "medians_por_cluster": {int(k): round(float(df.loc[km_prelim == k, "precio_m2_total_ars"].median()), 2) for k in range(3)},
        "anova_F": round(float(f_cl), 4),
        "anova_p": float(p_f_cl),
        "kruskal_H": round(float(h_cl), 4),
        "kruskal_p": float(p_h_cl),
        "decision": _interpret_p(float(p_h_cl)),
    }

    # 6. Chi-cuadrado de independencia: barrio vs moneda_origen (dolarización por barrio)
    ct = pd.crosstab(df.loc[df["barrio"].isin(top_barrios), "barrio"], df.loc[df["barrio"].isin(top_barrios), "moneda_origen"])
    chi2_val, p_chi2, dof, _ = stats.chi2_contingency(ct)
    tests["H6_chi2_barrio_vs_moneda"] = {
        "chi2": round(float(chi2_val), 4),
        "dof": int(dof),
        "p_value": float(p_chi2),
        "decision": _interpret_p(float(p_chi2)),
    }

    # 7. Correlaciones Spearman contra costo_total_ars y precio_m2_total_ars
    spearman_res = {}
    for col in CANDIDATE_FEATURES:
        r_tot, p_tot = stats.spearmanr(df[col], df["costo_total_ars"])
        r_m2, p_m2 = stats.spearmanr(df[col], df["precio_m2_total_ars"])
        spearman_res[col] = {
            "rho_costo_total": round(float(r_tot), 4),
            "p_costo_total": float(p_tot),
            "rho_precio_m2": round(float(r_m2), 4),
            "p_precio_m2": float(p_m2),
        }
    tests["spearman_correlations"] = spearman_res

    return tests


def compute_vif_table(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Calcula VIF usando matriz de correlación invertida y statsmodels como verificación."""
    X = df[cols].astype(float)
    # Estandarizar + agregar constante para statsmodels VIF
    X_std = (X - X.mean()) / X.std(ddof=0).replace(0, 1.0)
    X_const = np.column_stack([np.ones(len(X_std)), X_std.to_numpy()])
    vifs = {}
    for i, col in enumerate(cols):
        vifs[col] = float(variance_inflation_factor(X_const, i + 1))
    return pd.Series(vifs, name="VIF").sort_values(ascending=False)


def compute_feature_importance(df: pd.DataFrame, cols: list[str], target_col: str) -> pd.DataFrame:
    """Calcula Random Forest importance (en ARS y log-ARS) + Mutual Information."""
    X = df[cols].astype(float)
    y = df[target_col].astype(float)
    y_log = np.log1p(y)

    rf = RandomForestRegressor(n_estimators=400, max_depth=12, min_samples_leaf=3, random_state=42, n_jobs=-1)
    rf.fit(X, y)

    rf_log = RandomForestRegressor(n_estimators=400, max_depth=12, min_samples_leaf=3, random_state=42, n_jobs=-1)
    rf_log.fit(X, y_log)

    mi_raw = mutual_info_regression(X, y, random_state=42)
    mi_log = mutual_info_regression(X, y_log, random_state=42)

    imp = pd.DataFrame(
        {
            "feature": cols,
            "rf_importance": rf.feature_importances_,
            "rf_log_importance": rf_log.feature_importances_,
            "mutual_info": mi_raw,
            "mutual_info_log": mi_log,
        }
    )
    # Score combinado normalizado [0, 1] promediando RF y MI (robusto ante escala)
    for c in ["rf_importance", "rf_log_importance", "mutual_info", "mutual_info_log"]:
        max_v = imp[c].max()
        imp[f"{c}_norm"] = imp[c] / max_v if max_v > 0 else 0.0

    imp["combined_signal_score"] = (
        0.30 * imp["rf_importance_norm"]
        + 0.30 * imp["rf_log_importance_norm"]
        + 0.20 * imp["mutual_info_norm"]
        + 0.20 * imp["mutual_info_log_norm"]
    )
    return imp.sort_values("combined_signal_score", ascending=False).reset_index(drop=True)


def select_top_10_features(
    df: pd.DataFrame,
    imp_df: pd.DataFrame,
    vif_threshold: float = 5.0,
) -> tuple[list[str], dict[str, Any]]:
    """
    Selecciona exactamente 10 features respetando:
    1) Reducción de multicolinealidad (VIF < vif_threshold).
    2) Cobertura garantizada de pilares del negocio: físicas, apto_mascotas, score_amenities y 4 externalidades urbanas.
    3) Máximo score combinado de importancia (Random Forest + Mutual Information) para completar hasta 10.
    """
    signal_map = dict(zip(imp_df["feature"], imp_df["combined_signal_score"]))

    # Paso 1: Eliminación iterativa de multicolinealidad extrema, protegiendo las columnas de mayor señal dentro de cada par colineal
    remaining = list(CANDIDATE_FEATURES)
    elimination_log = []
    while True:
        vifs = compute_vif_table(df, remaining)
        max_feat = vifs.index[0]
        max_vif = float(vifs.iloc[0])
        if max_vif < vif_threshold or len(remaining) <= 10:
            break

        # Dentro de los candidatos con VIF >= threshold, preferir eliminar el de menor señal predictiva
        # pero nunca eliminar si dejaría vacío un pilar obligatorio
        high_vif = vifs[vifs >= vif_threshold].index.tolist()
        # Si hay empate o varios > umbral, buscamos entre los top-3 de mayor VIF cuál tiene menor señal y no es obligatorio
        candidates_to_drop = [f for f in high_vif[:4] if f not in MANDATORY_FEATURES]
        if not candidates_to_drop:
            candidates_to_drop = [max_feat]
        drop_feat = min(candidates_to_drop, key=lambda f: signal_map.get(f, 0.0))

        remaining.remove(drop_feat)
        elimination_log.append(
            {
                "dropped": drop_feat,
                "vif_when_dropped": round(float(vifs[drop_feat]), 4),
                "combined_signal_score": round(float(signal_map.get(drop_feat, 0.0)), 4),
            }
        )

    # Paso 2: Garantizar los pilares requeridos entre los sobrevivientes no colineales
    selected: list[str] = []
    for f in MANDATORY_FEATURES:
        if f in remaining and f not in selected:
            selected.append(f)

    # Elegir el mejor representante disponible de cada grupo de dominio urbano + físico
    for group_name, group_cols in DOMAIN_GROUPS.items():
        avail = [c for c in group_cols if c in remaining and c not in selected]
        if avail:
            best = max(avail, key=lambda c: signal_map.get(c, 0.0))
            selected.append(best)

    # Paso 3: Completar hasta 10 features con las de mayor señal predictiva entre las restantes sin VIF alto
    rest = [c for c in remaining if c not in selected]
    rest.sort(key=lambda c: signal_map.get(c, 0.0), reverse=True)
    for c in rest:
        if len(selected) >= 10:
            break
        selected.append(c)

    selected = selected[:10]
    final_vifs = compute_vif_table(df, selected)
    return selected, {
        "initial_vif": {k: round(float(v), 4) for k, v in compute_vif_table(df, CANDIDATE_FEATURES).items()},
        "vif_elimination_log": elimination_log,
        "surviving_low_vif_pool": remaining,
        "selected_features": selected,
        "final_vif": {k: round(float(v), 4) for k, v in final_vifs.items()},
    }


def generate_eda_plots(
    df: pd.DataFrame,
    imp_df: pd.DataFrame,
    selected_features: list[str],
    figures_dir: Path = config.FIGURES_DIR,
) -> list[str]:
    """Genera gráficos exploratorios de Fase 2 para respaldar decisiones estadísticas."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    saved = []

    # 1. Distribución de costo_total_ars y log1p(costo_total_ars)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    sns.histplot(df["costo_total_ars"] / 1e6, bins=35, kde=True, ax=axes[0], color="#1f77b4")
    axes[0].set_title("Distribución Costo Total Mensual (Millones ARS)")
    axes[0].set_xlabel("Millones ARS")
    sns.histplot(np.log1p(df["costo_total_ars"]), bins=35, kde=True, ax=axes[1], color="#2ca02c")
    axes[1].set_title("Distribución log1p(Costo Total Mensual)")
    axes[1].set_xlabel("log1p(ARS)")
    fig.tight_layout()
    p1 = figures_dir / "01_distribucion_target.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    saved.append(str(p1))

    # 2. Precio/m2 por macro-barrio y comparación ruido >65 dBA vs <=65 dBA
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    order_barrios = df.groupby("barrio")["precio_m2_total_ars"].median().sort_values(ascending=False).index
    sns.boxplot(data=df, x="precio_m2_total_ars", y="barrio", order=order_barrios, ax=axes[0], palette="viridis", hue="barrio", legend=False)
    axes[0].set_title("Precio/m² Total (ARS) por Barrio")
    axes[0].set_xlabel("ARS / m²")

    df_plot = df.copy()
    df_plot["zona_ruido"] = np.where(df_plot["ruido_db_promedio"] > 65.0, "Ruidosa (>65 dBA)", "Tranquila (<=65 dBA)")
    sns.boxplot(data=df_plot, x="zona_ruido", y="precio_m2_total_ars", ax=axes[1], palette="Set2", hue="zona_ruido", legend=False)
    axes[1].set_title("Precio/m² según Ruido Diurno (>65 vs <=65 dBA)")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("ARS / m²")
    fig.tight_layout()
    p2 = figures_dir / "02_barrios_y_ruido.png"
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    saved.append(str(p2))

    # 3. Feature Importance (RF + Mutual Information)
    top_imp = imp_df.head(15).sort_values("combined_signal_score", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#d62728" if f in selected_features else "#7f7f7f" for f in top_imp["feature"]]
    ax.barh(top_imp["feature"], top_imp["combined_signal_score"], color=colors)
    ax.set_title("Ranking Combinado de Señal Predictiva (RF + Mutual Info)\n(Rojo = Top 10 Seleccionadas sin Colinealidad)")
    ax.set_xlabel("Score Combinado Normalizado")
    fig.tight_layout()
    p3 = figures_dir / "03_feature_importance.png"
    fig.savefig(p3, dpi=140)
    plt.close(fig)
    saved.append(str(p3))

    # 4. Correlación de las 10 features seleccionadas + target
    corr_cols = selected_features + [config.TARGET_COL]
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(df[corr_cols].corr(), annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Matriz de Correlación: 10 Features Finales + Target")
    fig.tight_layout()
    p4 = figures_dir / "04_correlacion_top10.png"
    fig.savefig(p4, dpi=140)
    plt.close(fig)
    saved.append(str(p4))

    return saved


def run_phase1_and_phase2() -> dict[str, Any]:
    """Ejecuta Fase 1 (ETL + auditoría) y Fase 2 (EDA estadístico + selección de 10 features)."""
    df, audit_etl = etl.run_full_etl()

    # Guardar dataset enriquecido completo (con IDs, coordenadas, perfiles y flags para Fase 3)
    df.to_csv(config.OUTPUT_ENRICHED_CSV, index=False, encoding="utf-8")

    # Estadísticas descriptivas sobre target, auxiliares y pool candidato
    desc_cols = [
        "costo_total_ars",
        "alquiler_ars",
        "expensas_ars",
        "precio_m2_total_ars",
        *CANDIDATE_FEATURES,
    ]
    descriptive_stats = compute_descriptive_stats(df, desc_cols)
    hypothesis_tests = run_hypothesis_tests(df)
    imp_df = compute_feature_importance(df, CANDIDATE_FEATURES, config.TARGET_COL)
    selected_features, vif_report = select_top_10_features(df, imp_df, vif_threshold=5.0)

    # Exportar Producto 1 estrictamente acotado a <=10 features + target
    curated_cols = selected_features + [config.TARGET_COL]
    df_curated = df[curated_cols].copy()
    df_curated.to_csv(config.OUTPUT_CURATED_CSV, index=False, encoding="utf-8")

    plots = generate_eda_plots(df, imp_df, selected_features)

    report = {
        "business_questions": BUSINESS_QUESTIONS,
        "monetary_config": {
            "TIPO_CAMBIO_BASE": config.TIPO_CAMBIO_BASE,
            "FACTOR_IMPUESTOS_USD": config.FACTOR_IMPUESTOS_USD,
            "IMPUESTO_SELLOS_ALQUILER": config.IMPUESTO_SELLOS_ALQUILER,
        },
        "audit_etl": audit_etl,
        "descriptive_stats": descriptive_stats,
        "hypothesis_tests": hypothesis_tests,
        "multicollinearity_vif": vif_report,
        "feature_selection": {
            "selected_features": selected_features,
            "target": config.TARGET_COL,
            "final_vif": vif_report["final_vif"],
            "ranking_table": imp_df.round(5).to_dict(orient="records"),
        },
        "outputs": {
            "producto1_dataset_curado": str(config.OUTPUT_CURATED_CSV),
            "dataset_enriquecido_completo": str(config.OUTPUT_ENRICHED_CSV),
            "eda_stats": str(config.OUTPUT_EDA_JSON),
            "figures": plots,
        },
    }

    with open(config.OUTPUT_EDA_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report


if __name__ == "__main__":
    rep = run_phase1_and_phase2()
    audit = rep["audit_etl"]
    print("=== FASE 1: AUDITORÍA ETL ===")
    print(f"Registros crudos Zonaprop: {audit['zonaprop']['raw_records']}")
    print(f"Duplicados eliminados: {audit['zonaprop']['duplicates_removed']}")
    print(f"Descartados precio inválido: {audit['zonaprop']['dropped_invalid_price']}")
    print(f"Descartados coords fuera CABA: {audit['zonaprop']['dropped_out_of_caba_coords']} -> {audit['zonaprop']['out_of_caba_listing_ids']}")
    print(f"Descartados m2 inválidos: {audit['zonaprop']['dropped_invalid_m2']}")
    print(f"Registros válidos finales: {audit['final_rows']}")
    print(f"Imputaciones: {audit['zonaprop']['imputed_counts']}")
    print(f"Fuentes mascotas: {audit['zonaprop']['mascotas_source_counts']}")
    print(f"Ruido: matched_within={audit['ruido']['matched_within']}, imputed_nearest={audit['ruido']['imputed_nearest']}")
    print(f"Delitos: raw={audit['delitos']['delitos_raw_rows']}, nulls={audit['delitos']['delitos_null_coords']}, unrecoverable={audit['delitos']['delitos_unrecoverable_coords']}, valid={audit['delitos']['delitos_valid_rows']}")
    print(f"Escuelas familias filtradas: {audit['escuelas']['escuelas_familias_filtered']} / {audit['escuelas']['escuelas_raw_rows']}")
    print(f"Outliers IQR/Z-score: {audit['outliers']}")
    print("\n=== FASE 2: SELECCIÓN DE 10 FEATURES ===")
    print("Seleccionadas:", rep["feature_selection"]["selected_features"])
    print("VIF final:", rep["feature_selection"]["final_vif"])
    print("\n=== PRUEBAS DE HIPÓTESIS CLAVE ===")
    for k, v in rep["hypothesis_tests"].items():
        if k.startswith("H"):
            print(f"{k}: {v.get('decision')} | p={v.get('mann_whitney_p', v.get('kruskal_p', v.get('p_value'))):.4e}")
