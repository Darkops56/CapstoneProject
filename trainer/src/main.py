"""Entrypoint dual CLI / Apify SDK para el Actor de Entrenamiento Anual de Modelos MLOps."""

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from typing import Any
import pandas as pd
import requests

try:
    from trainer.src import gdrive_exporter, train_pipeline
except (ImportError, ModuleNotFoundError):
    from src import gdrive_exporter, train_pipeline

try:
    from apify import Actor
    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False


def load_dataset_from_input(actor_input: dict[str, Any]) -> pd.DataFrame:
    """Extrae o descarga el DataFrame de entrenamiento a partir del input."""
    # 1. Si se proveyó un array JSON en 'trainingData'
    raw_data = actor_input.get("trainingData")
    if raw_data and isinstance(raw_data, list):
        return pd.DataFrame(raw_data)

    # 2. Si se proveyó una URL a un CSV en 'trainingDataCsvUrl'
    csv_url = actor_input.get("trainingDataCsvUrl")
    if csv_url:
        print(f"[Trainer] Descargando dataset desde URL: {csv_url}")
        resp = requests.get(csv_url, timeout=60)
        resp.raise_for_status()
        return pd.read_csv(io.StringIO(resp.text))

    # 3. Si se especificó una ruta local en 'dataPath'
    data_path = actor_input.get("dataPath")
    if data_path and os.path.exists(data_path):
        return pd.read_csv(data_path)

    # 4. Fallback al archivo curado local del repo si existe
    default_candidates = [
        Path("etl/output/curated_caba_dataset.csv"),
        Path("../etl/output/curated_caba_dataset.csv"),
        Path("/usr/src/app/etl/output/curated_caba_dataset.csv"),
    ]
    for cand in default_candidates:
        if cand.exists():
            print(f"[Trainer] Usando dataset local predeterminado: {cand}")
            return pd.read_csv(cand)

    raise ValueError("ERR_NO_DATA: No se encontró ningún dataset válido en el input ni en el entorno local.")


async def _run_apify_mode() -> None:
    """Ejecución nativa serverless en el entorno de Apify."""
    if not HAS_APIFY:
        raise RuntimeError("El paquete 'apify' no está instalado en este entorno.")

    async with Actor:
        actor_input = await Actor.get_input() or {}
        min_r2 = float(actor_input.get("minR2Threshold", 0.80))
        min_samples = int(actor_input.get("minSamples", 500))
        gdrive_folder_id = actor_input.get("gdriveFolderId")
        gdrive_creds = actor_input.get("gdriveServiceAccountJson")
        target_col = actor_input.get("targetCol", train_pipeline.DEFAULT_TARGET_COL)

        artifacts_dir = Path("/tmp/trainer_artifacts")
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        try:
            print("[Trainer] Cargando dataset de entrenamiento anual...")
            df = load_dataset_from_input(actor_input)
            print(f"[Trainer] Dataset cargado con éxito: {len(df)} registros.")

            print(f"[Trainer] Iniciando entrenamiento y validación (min_r2={min_r2}, min_samples={min_samples})...")
            train_results = train_pipeline.run_training_pipeline(
                df=df,
                output_dir=artifacts_dir,
                min_samples=min_samples,
                min_r2=min_r2,
                target_col=target_col,
            )
            print(f"[Trainer] Entrenamiento exitoso. R2 obtenido: {train_results['metrics']['r2']}")

            # Exportación a Google Drive
            export_result = {}
            if gdrive_folder_id:
                print(f"[Trainer] Exportando artefactos a Google Drive folder: {gdrive_folder_id}...")
                export_result = gdrive_exporter.export_version_to_gdrive(
                    credentials_info=gdrive_creds,
                    registry_folder_id=gdrive_folder_id,
                    artifacts_dir=artifacts_dir,
                    metrics=train_results["metrics"],
                    dry_run=False,
                )
                print(f"[Trainer] Versión {export_result.get('version')} exportada a Google Drive con éxito.")
            else:
                print("[Trainer] INFO: gdriveFolderId no especificado. Omitiendo subida a Drive.")

            final_output = {
                "status": "success",
                "training_results": train_results,
                "drive_export": export_result,
            }

            await Actor.push_data(final_output)
            await Actor.set_value("OUTPUT", final_output)
            await Actor.set_status_message(f"Entrenamiento completado: R2={train_results['metrics']['r2']}")

        except train_pipeline.InsufficientDataError as e:
            print(f"[Trainer] WARN: {e}")
            await Actor.set_status_message(f"Abortado: {e}")
            await Actor.set_value("OUTPUT", {"status": "error", "error": str(e)})
            sys.exit(1)
        except train_pipeline.MetricRegressionError as e:
            print(f"[Trainer] REGRESSION ERROR: {e}")
            await Actor.set_status_message(f"Regresión detectada: {e}")
            await Actor.set_value("OUTPUT", {"status": "error", "error": str(e)})
            sys.exit(2)
        except Exception as e:
            print(f"[Trainer] ERROR INESPERADO: {e}")
            await Actor.set_status_message(f"Error: {e}")
            await Actor.set_value("OUTPUT", {"status": "error", "error": str(e)})
            sys.exit(3)


def run_cli_mode() -> int:
    """Ejecución por línea de comandos para desarrollo local y pruebas."""
    parser = argparse.ArgumentParser(description="CLI Runner para el Trainer MLOps")
    parser.add_argument("--data-path", type=str, default="etl/output/curated_caba_dataset.csv")
    parser.add_argument("--gdrive-folder-id", type=str, default="")
    parser.add_argument("--gdrive-creds", type=str, default="")
    parser.add_argument("--min-r2", type=float, default=0.80)
    parser.add_argument("--min-samples", type=int, default=500)
    parser.add_argument("--output-dir", type=str, default="trainer/artifacts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_payload = {
        "dataPath": args.data_path,
        "gdriveFolderId": args.gdrive_folder_id,
        "gdriveServiceAccountJson": args.gdrive_creds,
        "minR2Threshold": args.min_r2,
        "minSamples": args.min_samples,
    }

    try:
        print("[CLI Trainer] Cargando dataset...")
        df = load_dataset_from_input(input_payload)
        output_dir = Path(args.output_dir)

        print("[CLI Trainer] Ejecutando pipeline de entrenamiento...")
        results = train_pipeline.run_training_pipeline(
            df=df,
            output_dir=output_dir,
            min_samples=args.min_samples,
            min_r2=args.min_r2,
        )
        print(f"[CLI Trainer] Entrenamiento exitoso. Métricas: {results['metrics']}")

        if args.gdrive_folder_id or args.dry_run:
            print("[CLI Trainer] Exportando versión a Google Drive...")
            exp = gdrive_exporter.export_version_to_gdrive(
                credentials_info=args.gdrive_creds,
                registry_folder_id=args.gdrive_folder_id,
                artifacts_dir=output_dir,
                metrics=results["metrics"],
                dry_run=args.dry_run,
            )
            print(f"[CLI Trainer] Exportación finalizada: {exp['status']} (Versión {exp.get('version')})")

        return 0
    except (train_pipeline.InsufficientDataError, train_pipeline.MetricRegressionError) as e:
        print(f"[CLI Trainer] Error esperado de validación: {e}")
        return 1
    except Exception as e:
        print(f"[CLI Trainer] Error fatal: {e}")
        return 2


def main() -> None:
    """Punto de entrada: detecta si corre en contenedor de Apify o CLI estándar."""
    is_apify = (
        bool(os.environ.get("APIFY_IS_AT_HOME"))
        or bool(os.environ.get("APIFY_TOKEN"))
        or "APIFY_CONTAINER_URL" in os.environ
    )

    if is_apify and HAS_APIFY:
        asyncio.run(_run_apify_mode())
    else:
        sys.exit(run_cli_mode())


if __name__ == "__main__":
    main()
