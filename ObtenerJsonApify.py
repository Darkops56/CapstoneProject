

import requests, json

TOKEN = "apify_api_tvBzojyeWbJfBirHGEvj5ttNK4mSoQ0J39JV"
ACTOR_ID = "memo23~zonaprop-scraper"

runs = requests.get(
    f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={TOKEN}&limit=20&desc=true"
).json()["data"]["items"]

consolidado, vistos = [], set()
for r in runs:
    if r["status"] == "SUCCEEDED":
        items = requests.get(
            f"https://api.apify.com/v2/datasets/{r['defaultDatasetId']}/items?token={TOKEN}"
        ).json()
        for it in items:
            pid = it.get("listingId")
            if pid and pid not in vistos and "alquiler" in str(it.get("list_operation_name", "")).lower():
                vistos.add(pid)
                consolidado.append(it)

with open("zonaprop_alquileres_caba_1000.json", "w", encoding="utf-8") as f:
    json.dump(consolidado, f, ensure_ascii=False, indent=2)

print(f"Listo: {len(consolidado)} alquileres únicos guardados en zonaprop_alquileres_caba_1000.json")