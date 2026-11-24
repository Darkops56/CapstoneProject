"""Script determinista para benchmark empírico de tiempo, memoria y costo computacional en Apify.

Mide el rendimiento del pipeline de inferencia (`actors/inference/src/pipeline.py`)
y calcula las Compute Units (CUs) y costo en USD bajo la política oficial de facturación de Apify.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import resource
import sys
import time
import tracemalloc
from typing import Any, Dict, List

# Asegurar que el root del repositorio esté en sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from actors.inference.src.pipeline import curate_and_enrich, load_geo_cache, predict_and_score

DEFAULT_APIFY_CU_RATE = 0.20  # USD por Compute Unit (Plan Free / Starter)
DEFAULT_CONTAINER_MEMORY_MB = 1024  # 1.0 GB RAM / 0.25 vCPU
CONTAINER_OVERHEAD_SECONDS = 2.0  # Estimación de inicialización de contenedor e I/O


def generate_synthetic_caba_batch(n_records: int) -> List[Dict[str, Any]]:
    """Genera un lote sintético representativo de propiedades dentro del polígono de CABA."""
    sample_base = {
        "id": "BENCH_RECORD",
        "title": "Departamento 2 ambientes con balcón y cochera en Palermo",
        "description": "Edificio con amenities: piscina, sum, gimnasio, seguridad 24hs, apto mascotas y profesional.",
        "price": 450000.0,
        "currency": "ARS",
        "expenses": 75000.0,
        "latitude": -34.588,
        "longitude": -58.430,
        "rooms": 2,
        "bathrooms": 1,
        "garages": 1,
        "surface_total": 52.0,
    }

    batch: List[Dict[str, Any]] = []
    for i in range(n_records):
        # Variación espacial determinista dentro de CABA
        lat_offset = ((i % 100) - 50) * 0.001
        lon_offset = (((i // 100) % 100) - 50) * 0.001
        rec = dict(
            sample_base,
            id=f"MLA_{i+1:06d}",
            latitude=-34.588 + lat_offset,
            longitude=-58.430 + lon_offset,
            price=sample_base["price"] + (i % 20) * 10000.0,
        )
        batch.append(rec)
    return batch


def run_inference_benchmark(
    batch_sizes: List[int] | None = None,
    memory_mb: int = DEFAULT_CONTAINER_MEMORY_MB,
    apify_cu_rate: float = DEFAULT_APIFY_CU_RATE,
    container_overhead_s: float = CONTAINER_OVERHEAD_SECONDS,
) -> Dict[int, Dict[str, Any]]:
    """Ejecuta la medición empírica de tiempo y recursos para distintos tamaños de lote."""
    if batch_sizes is None:
        batch_sizes = [1000, 10000]

    # Pre-calentamiento (Carga en memoria de Parquet geoespacial y artefactos .joblib)
    load_geo_cache()
    warmup_batch = generate_synthetic_caba_batch(10)
    _ = predict_and_score(curate_and_enrich(warmup_batch))

    results: Dict[int, Dict[str, Any]] = {}

    for n in batch_sizes:
        if n <= 0:
            raise ValueError(f"ERR_INVALID_BATCH_SIZE: el tamaño de lote debe ser > 0, recibido {n}")

        batch = generate_synthetic_caba_batch(n)

        tracemalloc.start()
        t0 = time.perf_counter()
        df_curated = curate_and_enrich(batch)
        t_curate = time.perf_counter() - t0

        t1 = time.perf_counter()
        df_scored = predict_and_score(df_curated)
        t_score = time.perf_counter() - t1

        t_total = t_curate + t_score
        current_mem, peak_traced = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Memoria residente máxima del proceso
        max_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

        # Cálculo oficial de Apify: CU = (RAM en GB) * (duración en horas)
        ram_gb = memory_mb / 1024.0
        duracion_apify_s = t_total + container_overhead_s
        duracion_apify_h = duracion_apify_s / 3600.0
        cu = ram_gb * duracion_apify_h
        costo_usd = cu * apify_cu_rate

        results[n] = {
            "n_records": n,
            "t_curate_s": round(t_curate, 4),
            "t_score_s": round(t_score, 4),
            "t_compute_total_s": round(t_total, 4),
            "t_apify_run_est_s": round(duracion_apify_s, 4),
            "ram_allocated_mb": memory_mb,
            "ram_peak_process_mb": round(max_rss_mb, 1),
            "ram_peak_traced_mb": round(peak_traced / (1024.0 * 1024.0), 2),
            "compute_units_cu": round(cu, 6),
            "cost_per_run_usd": round(costo_usd, 6),
            "cost_monthly_4runs_usd": round(costo_usd * 4, 6),
            "output_rows": len(df_scored),
        }

    return results


def print_benchmark_report(results: Dict[int, Dict[str, Any]]) -> None:
    """Imprime el reporte estructurado y la ficha comparativa."""
    print("=" * 80)
    print(" 🏙️ BENCHMARK DE COSTO COMPUTACIONAL E INFERENCIA (APIFY SERVERLESS)")
    print("=" * 80)
    for n, r in results.items():
        print(f"\n📦 LOTE EVALUADO: {n:,} REGISTROS (CABA)")
        print(f"  • Tiempo Neto Cómputo:        {r['t_compute_total_s']:.3f} s  (Curación: {r['t_curate_s']:.3f}s | Inferencia: {r['t_score_s']:.3f}s)")
        print(f"  • Tiempo Estimado Corrida:    {r['t_apify_run_est_s']:.3f} s  (incluye overhead I/O)")
        print(f"  • Memoria Asignada Contenedor:{r['ram_allocated_mb']} MB (1.0 GB RAM / 0.25 vCPU)")
        print(f"  • Memoria Residente Pico:     {r['ram_peak_process_mb']} MB (Headroom disponible: {r['ram_allocated_mb'] - r['ram_peak_process_mb']:.1f} MB)")
        print(f"  • Compute Units (CUs):        {r['compute_units_cu']:.6f} CU")
        print(f"  • Costo Estimado por Corrida: ${r['cost_per_run_usd']:.6f} USD (@ ${DEFAULT_APIFY_CU_RATE:.2f}/CU)")
        print(f"  • Costo Mensual (4 corridas): ${r['cost_monthly_4runs_usd']:.6f} USD (100% Free Tier)")
    print("\n" + "=" * 80)
    print(" TOKEN DE ESTADO: BENCHMARK_SUCCESS")
    print("=" * 80)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark de costo computacional e inferencia en Apify.")
    parser.add_argument("--records", type=str, default="1000,10000", help="Lista de tamaños de lote separados por coma.")
    parser.add_argument("--memory-mb", type=int, default=DEFAULT_CONTAINER_MEMORY_MB, help="Memoria del contenedor en MB.")
    parser.add_argument("--cu-rate", type=float, default=float(os.getenv("APIFY_CU_RATE", DEFAULT_APIFY_CU_RATE)), help="Tarifa USD por CU.")
    args = parser.parse_args()

    batch_sizes = [int(x.strip()) for x in args.records.split(",") if x.strip()]
    results = run_inference_benchmark(batch_sizes=batch_sizes, memory_mb=args.memory_mb, apify_cu_rate=args.cu_rate)
    print_benchmark_report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
