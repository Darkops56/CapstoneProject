"""Entrypoint dual CLI / Apify SDK para el Actor de Inferencia y Curación."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
import pandas as pd

try:
    from . import pipeline
except (ImportError, ValueError):
    try:
        from actors.inference.src import pipeline
    except (ImportError, ModuleNotFoundError):
        from src import pipeline

try:
    from apify import Actor
    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False


def run_pipeline(
    input_data: list[dict[str, Any]],
    artifacts_dir: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta el pipeline completo de curación, cruce geoespacial e inferencia."""
    if not input_data:
        return []

    print(f"[Actor] Iniciando pipeline para {len(input_data)} propiedades...")
    df_curated = pipeline.curate_and_enrich(input_data)
    print(f"[Actor] Curación y cruce geoespacial completados ({len(df_curated)} registros)")

    df_scored = pipeline.predict_and_score(df_curated, artifacts_dir=artifacts_dir)
    print(f"[Actor] Inferencia y cálculo de scores finalizados exitosamente")

    return df_scored.to_dict(orient="records")


async def _resolve_dynamic_models(actor_input: dict[str, Any]) -> Path | None:
    """Descarga modelos actualizados desde un Key-Value Store de Apify si se indica en el input."""
    store_id = actor_input.get("modelKvStoreId")
    store_name = actor_input.get("modelStoreName")
    if not store_id and not store_name:
        return None

    required_files = ("kmeans_model.joblib", "xgb_price_model.joblib", "model_metadata.joblib")
    target_dir = Path("/tmp/dynamic_models")
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Bajo LIMITED_PERMISSIONS se prioriza store_id que cuenta con resourcePermissions delegados
        kv_store = await Actor.open_key_value_store(id=store_id) if store_id else await Actor.open_key_value_store(name=store_name)
        for fname in required_files:
            content = await kv_store.get_value(fname)
            if not content or not isinstance(content, (bytes, bytearray)):
                print(f"[Actor] WARN: Falta '{fname}' en KV Store ({store_id or store_name}); usando fallback local.")
                return None
            (target_dir / fname).write_bytes(bytes(content))
        print(f"[Actor] Modelos dinámicos cargados desde Apify KV Store: {store_id or store_name}")
        return target_dir
    except Exception as exc:
        print(f"[Actor] WARN: Error leyendo KV Store ({store_id or store_name}): {exc}. Usando fallback local.")
        return None


async def _run_apify_mode() -> None:
    """Ejecución nativa dentro de la infraestructura de la nube de Apify."""
    if not HAS_APIFY:
        raise RuntimeError("El paquete 'apify' no está instalado en este entorno.")

    async with Actor:
        actor_input = await Actor.get_input() or {}
        limit = int(actor_input.get("limit", 1000))
        dataset_id = actor_input.get("datasetId")
        raw_items = actor_input.get("properties")

        # Si se proveyó un datasetId de Zonaprop, descargar los items
        if dataset_id and not raw_items:
            print(f"[Actor] Descargando items desde datasetId: {dataset_id}...")
            try:
                # Patrón idiomático de Apify SDK para LIMITED_PERMISSIONS con resourcePermissions: ["READ"]
                dataset = await Actor.open_dataset(id=dataset_id)
                dataset_items = await dataset.get_data(limit=limit)
                raw_items = dataset_items.items
            except Exception as exc_open:
                print(f"[Actor] INFO: Fallback a client.dataset tras open_dataset: {exc_open}")
                client = Actor.new_client()
                dataset_client = client.dataset(dataset_id)
                dataset_items = await dataset_client.list_items(limit=limit)
                raw_items = dataset_items.items

        if not raw_items:
            print("[Actor] WARN: No se recibieron datos de entrada en el Actor.")
            await Actor.set_status_message("WARN: Entrada vacía")
            return

        # Aplicar límite si es necesario
        if limit and len(raw_items) > limit:
            raw_items = raw_items[:limit]

        dynamic_models_dir = await _resolve_dynamic_models(actor_input)
        results = run_pipeline(raw_items, artifacts_dir=dynamic_models_dir)

        print(f"[Actor] Guardando {len(results)} registros en el dataset por defecto de Apify...")
        await Actor.push_data(results)
        await Actor.set_status_message(f"Completado exitosamente: {len(results)} registros procesados")


def main() -> None:
    """Función principal con soporte dual CLI local y Apify runtime."""
    parser = argparse.ArgumentParser(description="Actor de Curado e Inferencia Zonaprop CABA")
    parser.add_argument("--input", "-i", type=str, help="Ruta al archivo JSON con propiedades crudas")
    parser.add_argument("--output", "-o", type=str, help="Ruta de salida para el archivo CSV o JSON")
    parser.add_argument("--limit", "-l", type=int, default=1000, help="Límite máximo de propiedades")
    parser.add_argument("--apify", action="store_true", help="Forzar ejecución en modo Apify SDK")

    args = parser.parse_args()

    # Modo 1: CLI local
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: No existe el archivo de entrada '{input_path}'", file=sys.stderr)
            sys.exit(1)

        with open(input_path, "r", encoding="utf-8") as f:
            raw_items = json.load(f)

        if args.limit and len(raw_items) > args.limit:
            raw_items = raw_items[:args.limit]

        results = run_pipeline(raw_items)

        df_out = pd.DataFrame(results)
        output_path = Path(args.output) if args.output else Path("resultados_inferencia_local.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix.lower() == ".json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        else:
            df_out.to_csv(output_path, index=False, encoding="utf-8")

        print(f"Éxito: {len(df_out)} registros guardados en '{output_path}'")
        return

    # Modo 2: Apify Cloud / Docker Container
    if os.environ.get("APIFY_IS_AT_HOME") or args.apify:
        asyncio.run(_run_apify_mode())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
