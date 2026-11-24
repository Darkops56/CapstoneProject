"""Tests automatizados deterministas para el SLA de costo computacional e inferencia."""

import pytest
from scripts.benchmark_inference_cost import (
    DEFAULT_APIFY_CU_RATE,
    DEFAULT_CONTAINER_MEMORY_MB,
    generate_synthetic_caba_batch,
    run_inference_benchmark,
)


def test_synthetic_caba_batch_generation():
    """Valida que la generación de lote sintético produzca registros íntegros dentro de CABA."""
    batch_100 = generate_synthetic_caba_batch(100)
    assert len(batch_100) == 100
    for item in batch_100:
        assert item["id"].startswith("MLA_")
        assert -34.70 <= item["latitude"] <= -34.52
        assert -58.54 <= item["longitude"] <= -58.34
        assert item["price"] > 0
        assert item["rooms"] >= 1


def test_inference_benchmark_sla_1000_records():
    """Valida que un lote estándar de 1,000 registros cumpla los umbrales de SLA estipulados."""
    results = run_inference_benchmark(batch_sizes=[1000], memory_mb=DEFAULT_CONTAINER_MEMORY_MB)
    assert 1000 in results
    r = results[1000]

    # SLA 1: Tiempo neto de cómputo < 5.0 segundos
    assert r["t_compute_total_s"] < 5.0, (
        f"ERR_INFERENCE_SLA_EXCEEDED: Tiempo neto {r['t_compute_total_s']}s >= 5.0s"
    )

    # SLA 2: Tiempo de corrida estimado en Apify < 8.0 segundos
    assert r["t_apify_run_est_s"] < 8.0

    # SLA 3: Memoria residente pico < 1,024 MB (sin OOM en contenedor asignado)
    assert r["ram_peak_process_mb"] < DEFAULT_CONTAINER_MEMORY_MB

    # SLA 4: Consumo de Compute Units < 0.002 CU
    assert r["compute_units_cu"] < 0.002
    assert r["cost_per_run_usd"] < 0.0004
    assert r["output_rows"] == 1000


def test_inference_benchmark_sla_10000_records():
    """Valida que el lote extendido de 10,000 registros cumpla los umbrales de SLA estipulados."""
    results = run_inference_benchmark(batch_sizes=[10000], memory_mb=DEFAULT_CONTAINER_MEMORY_MB)
    assert 10000 in results
    r = results[10000]

    # SLA 1: Tiempo neto de cómputo < 10.0 segundos
    assert r["t_compute_total_s"] < 10.0, (
        f"ERR_INFERENCE_SLA_EXCEEDED: Tiempo neto {r['t_compute_total_s']}s >= 10.0s"
    )

    # SLA 2: Memoria residente pico < 1,024 MB
    assert r["ram_peak_process_mb"] < DEFAULT_CONTAINER_MEMORY_MB

    # SLA 3: Consumo de Compute Units < 0.005 CU
    assert r["compute_units_cu"] < 0.005
    assert r["cost_per_run_usd"] < 0.0010
    assert r["output_rows"] == 10000


def test_invalid_batch_size_raises_value_error():
    """Valida el manejo de frontera ante tamaños de lote inválidos."""
    with pytest.raises(ValueError, match="ERR_INVALID_BATCH_SIZE"):
        run_inference_benchmark(batch_sizes=[0])
