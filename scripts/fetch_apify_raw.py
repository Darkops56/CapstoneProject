"""Script auxiliar para descargar resultados crudos del scraper de Zonaprop desde Apify.
Uso:
    export APIFY_TOKEN="tu_token_aqui"
    python scripts/fetch_apify_raw.py
"""
import os
import sys
import json
import requests

TOKEN = os.environ.get("APIFY_TOKEN")
if not TOKEN:
    print("ERROR: La variable de entorno APIFY_TOKEN no está configurada.", file=sys.stderr)
    print("Ejecute: export APIFY_TOKEN='tu_token_aqui' antes de correr este script.", file=sys.stderr)
    sys.exit(1)

ACTOR_ID = os.environ.get("APIFY_ACTOR_ID", "memo23~zonaprop-scraper")

print(f"Consultando ejecuciones del actor {ACTOR_ID}...")
resp = requests.get(
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={TOKEN}&limit=20&desc=true",
    timeout=30,
)
resp.raise_for_status()
runs = resp.json().get("data", {}).get("items", [])

consolidado, vistos = [], set()
for r in runs:
    if r.get("status") == "SUCCEEDED":
        dataset_id = r.get("defaultDatasetId")
        if not dataset_id:
            continue
        items_resp = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={TOKEN}",
            timeout=60,
        )
        if items_resp.status_code == 200:
            items = items_resp.json()
            for it in items:
                pid = it.get("listingId")
                if pid and pid not in vistos and "alquiler" in str(it.get("list_operation_name", "")).lower():
                    vistos.add(pid)
                    consolidado.append(it)

output_filename = "zonaprop_alquileres_caba_1000.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(consolidado, f, ensure_ascii=False, indent=2)

print(f"Listo: {len(consolidado)} alquileres únicos guardados en {output_filename}")
