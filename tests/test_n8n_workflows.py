"""Suite de aserciones semánticas deterministas para workflows de n8n."""

import json
from pathlib import Path
import pytest

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows" / "n8n"


@pytest.fixture
def monthly_workflow() -> dict:
    wf_path = WORKFLOWS_DIR / "workflow_mensual_zonaprop_inferencia.json"
    with open(wf_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def annual_workflow() -> dict:
    wf_path = WORKFLOWS_DIR / "workflow_anual_auditoria_gcba.json"
    with open(wf_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_monthly_workflow_semantic_invariants(monthly_workflow):
    """Verifica cron mensual, timeout 300s, chequeo de SUCCEEDED, clean=true y binaryData en Drive."""
    nodes = {n["id"]: n for n in monthly_workflow.get("nodes", [])}
    nodes_by_name = {n["name"]: n for n in monthly_workflow.get("nodes", [])}

    # 1. Trigger Cron Mensual
    trigger = nodes.get("schedule-trigger-mensual") or nodes_by_name.get("Cron Mensual (Día 1 03:00)")
    assert trigger is not None
    rule_interval = trigger["parameters"]["rule"]["interval"][0]
    cron_expr = rule_interval.get("expression") or ""
    # Debe ser cron explícito 0 3 1 * * o configuración equivalente de día 1 a las 03:00
    assert (
        cron_expr == "0 3 1 * *"
        or (rule_interval.get("triggerAtDayOfMonth") == 1 and rule_interval.get("triggerAtHour") == 3)
    )

    # 2. Timeout en Scraper HTTP Request
    scraper = nodes.get("apify-scraper-zonaprop") or nodes_by_name.get("Apify: Scraper Zonaprop (1000 items)")
    assert scraper is not None
    assert "waitForFinish=300" in scraper["parameters"]["url"], "El scraper debe configurar waitForFinish=300"

    # 3. Circuit Breaker debe validar status === 'SUCCEEDED'
    cb_node = nodes.get("circuit-breaker-check") or nodes_by_name.get("Circuit Breaker & Hash Check")
    assert cb_node is not None
    code = cb_node["parameters"]["jsCode"]
    assert "SUCCEEDED" in code, "Circuit Breaker debe validar defensivamente que el status sea SUCCEEDED"
    assert "ERR_SCRAPER_INCOMPLETE_BATCH" in code
    assert "SKIP_IDENTICAL_DATASET" in code

    # 4. Descarga CSV con &clean=true
    csv_node = nodes.get("download-curated-csv") or nodes_by_name.get("Descargar CSV Enriquecido")
    assert csv_node is not None
    assert "clean=true" in csv_node["parameters"]["url"], "La descarga CSV debe incluir el parámetro clean=true"

    # 5. Google Drive Upload con binaryData o folderId configurado
    drive_node = nodes.get("google-drive-upload") or nodes_by_name.get("Google Drive: Guardar CSV Mensual")
    assert drive_node is not None
    assert (
        drive_node["parameters"].get("binaryData") is True
        or drive_node["parameters"].get("folderId") is not None
    ), "El nodo Google Drive debe tener binaryData: true o folderId configurado"

    # 6. Google Drive Search para retención trimestral
    search_node = nodes_by_name.get("Google Drive: Listar Archivos 01_mensual_enriquecido")
    assert search_node is not None
    assert search_node["parameters"].get("resource") == "fileFolder"
    assert search_node["parameters"].get("operation") == "search"
    assert search_node["parameters"].get("searchMethod") == "query"

    # 7. Purga a papelera con resource: file y operation: delete
    purge_node = nodes_by_name.get("Google Drive: Purgar Excedente a Papelera")
    assert purge_node is not None
    assert purge_node["parameters"].get("resource") == "file"
    assert purge_node["parameters"].get("operation") == "delete"

    # 8. Actor mensual consume modelo dinámico desde mlops-production-models
    inf_node = nodes_by_name.get("Apify: Actor Curado & Inferencia")
    assert inf_node is not None
    assert "mlops-production-models" in inf_node["parameters"].get("jsonBody", ""), (
        "El actor mensual debe consumir modelos dinámicos desde mlops-production-models"
    )



def test_annual_workflow_semantic_invariants(annual_workflow):
    """Verifica cron anual 0 4 1 3 *, compuerta de idempotencia CKAN y binaryData en Drive."""
    nodes = {n["id"]: n for n in annual_workflow.get("nodes", [])}
    nodes_by_name = {n["name"]: n for n in annual_workflow.get("nodes", [])}

    # 1. Trigger Cron Anual
    trigger = nodes.get("schedule-trigger-anual") or nodes_by_name.get("Cron Anual (1 de Marzo)")
    assert trigger is not None
    rule_interval = trigger["parameters"]["rule"]["interval"][0]
    assert rule_interval.get("field") == "cronExpression", "El scheduleTrigger anual debe usar cronExpression"
    assert rule_interval.get("expression") in ["0 4 1 3 *", "0 0 3 1 1 1"], "Expresión cron anual no esperada"

    # 2. Evaluación de Metadatos e Idempotencia
    meta_node = nodes.get("parse-ckan-metadata") or nodes_by_name.get("Evaluar Metadatos & URL Descarga")
    assert meta_node is not None
    code = meta_node["parameters"]["jsCode"]
    assert "getWorkflowStaticData" in code, "Debe interactuar con el staticData del workflow para idempotencia"
    assert "metadataModified" in code or "metadata_modified" in code

    # 3. Compuerta IF para filtrar sin novedades
    if_node = next((n for n in annual_workflow.get("nodes", []) if n.get("type") == "n8n-nodes-base.if"), None)
    assert if_node is not None, "El workflow anual debe contener una compuerta IF de novedad"

    # 4. Presencia del token SKIP_NO_ANNUAL_UPDATE
    all_json_str = json.dumps(annual_workflow)
    assert "SKIP_NO_ANNUAL_UPDATE" in all_json_str, "El flujo debe contemplar el token canónico SKIP_NO_ANNUAL_UPDATE"

    # 5. Google Drive Upload con binaryData o folderId configurado
    drive_node = nodes.get("google-drive-upload-raw") or nodes_by_name.get("Google Drive: Resguardar en Raw Anual")
    assert drive_node is not None
    assert (
        drive_node["parameters"].get("binaryData") is True
        or drive_node["parameters"].get("folderId") is not None
    ), "El nodo Google Drive debe tener binaryData: true o folderId configurado"


def test_annual_workflow_convergent_trainer_and_resilience(annual_workflow):
    """Verifica el pipeline anual multi-dataset convergente: 4 datasets GCBA, Continue on Fail, Merge+Consolidar y Actor Trainer."""
    nodes = annual_workflow.get("nodes", [])
    nodes_by_name = {n["name"]: n for n in nodes}
    all_json_str = json.dumps(annual_workflow)

    # 1. Catálogo de los 4 datasets oficiales de GCBA
    catalog_node = nodes_by_name.get("Definir Catálogo Datasets GCBA")
    assert catalog_node is not None, "Debe existir el nodo Definir Catálogo Datasets GCBA"
    catalog_code = catalog_node["parameters"].get("jsCode", "")
    for slug in ("delitos", "bocas-subte", "mapa-ruido", "establecimientos-educativos"):
        assert slug in catalog_code, f"El catálogo anual debe incluir el dataset CKAN '{slug}'"

    # 2. Nodo CKAN debe tener resiliencia (Continue on Fail / onError) y timeout explícito <= 30000ms
    ckan_node = (
        nodes_by_name.get("CKAN API: Consultar Datasets GCBA")
        or nodes_by_name.get("CKAN API: Consultar Delitos CABA")
    )
    assert ckan_node is not None
    assert (
        ckan_node.get("continueOnFail") is True
        or ckan_node.get("onError") in ("continueRegularOutput", "continueErrorOutput")
    ), "El nodo CKAN API debe soportar degradación elegante (continueOnFail / onError)"
    assert ckan_node["parameters"].get("options", {}).get("timeout", 999999) <= 30000, (
        "El nodo CKAN API debe configurar timeout <= 30000ms"
    )
    assert "package_show?id={{ $json.datasetId }}" in ckan_node["parameters"].get("url", ""), (
        "El nodo CKAN debe parametrizar dinámicamente el datasetId"
    )

    # 3. Token canónico WARN_GCBA_UNAVAILABLE ante caída o fallo de CKAN
    assert "WARN_GCBA_UNAVAILABLE" in all_json_str, (
        "El workflow anual debe emitir WARN_GCBA_UNAVAILABLE cuando falla CKAN"
    )

    # 4. Nodo Apify: Actor Trainer conectado con waitForFinish=360 y auth Header
    trainer_node = (
        nodes_by_name.get("Apify: Actor Trainer")
        or nodes_by_name.get("Apify: Actor Reentrenamiento Anual (trainer)")
    )
    assert trainer_node is not None, "Debe existir el nodo HTTP de invocación al Actor Trainer"
    assert "mlops-annual-trainer" in trainer_node["parameters"].get("url", ""), (
        "La URL del Trainer debe apuntar a mlops-annual-trainer"
    )
    assert "waitForFinish=360" in trainer_node["parameters"].get("url", ""), (
        "El nodo Trainer debe configurar waitForFinish=360"
    )
    assert trainer_node["parameters"].get("options", {}).get("timeout") == 360000, (
        "El timeout HTTP del Trainer debe ser 360000ms"
    )

    # 5. Convergencia a través de Merge + barrera de 1 solo trigger hacia Actor Trainer
    connections = annual_workflow.get("connections", {})
    merge_node = nodes_by_name.get("Merge: Converger Auditoría GCBA")
    consolidar_node = nodes_by_name.get("Consolidar Auditoría Anual (1 Trigger)")
    assert merge_node is not None, "Debe existir el nodo Merge: Converger Auditoría GCBA"
    assert consolidar_node is not None, "Debe existir la barrera Consolidar Auditoría Anual (1 Trigger)"
    assert consolidar_node["parameters"].get("mode") == "runOnceForAllItems", (
        "La barrera de consolidación debe correr en modo runOnceForAllItems para disparar el Trainer exactamente 1 vez"
    )

    sources_to_merge = [
        src
        for src, outs in connections.items()
        for branch in outs.get("main", [])
        for target in branch
        if target.get("node") == merge_node["name"]
    ]
    assert len(sources_to_merge) >= 2, (
        f"El nodo Merge debe recibir ambas ramas (actualización y fallback/skip). Recibidos: {sources_to_merge}"
    )
    consolidar_targets = [
        target.get("node")
        for branch in connections.get(consolidar_node["name"], {}).get("main", [])
        for target in branch
    ]
    assert "Google Drive: Listar CSVs de Entrenamiento" in consolidar_targets, (
        "La barrera de consolidación debe disparar la carga de CSVs de entrenamiento desde Google Drive"
    )

    # 6. Flujo Opción A (OAuth2 Drive -> Trainer -> KV Store -> Drive 03_model_registry + Promoción a Producción)
    for expected_node in (
        "Google Drive: Listar CSVs de Entrenamiento",
        "Google Drive: Descargar CSVs de Entrenamiento",
        "Preparar Payload de Entrenamiento",
        "Apify: Abrir Store Producción",
        "Verificar Trainer & Listar Artefactos",
        "Apify: Descargar Artefactos del Modelo",
        "Google Drive: Guardar Modelo en 03_model_registry",
        "Apify: Publicar Modelo en Producción",
    ):
        assert expected_node in nodes_by_name, f"Falta el nodo de Opción A: '{expected_node}'"

    assert "trainingDataCsvText" in all_json_str
    assert "defaultKeyValueStoreId" in all_json_str
    assert "03_model_registry" in all_json_str
    assert "mlops-production-models" in all_json_str


def test_unified_pipeline_dual_retention_and_trainer():
    """Verifica que el lienzo unificado incluya retención dual (04_historico_alquileres_anual) y Actor Trainer."""
    wf_path = WORKFLOWS_DIR / "Pipeline Completo Anual y Mensual.json"
    with open(wf_path, "r", encoding="utf-8") as f:
        unified_wf = json.load(f)

    all_json_str = json.dumps(unified_wf)
    assert "04_historico_alquileres_anual" in all_json_str, (
        "El pipeline unificado debe contemplar el acumulador anual 04_historico_alquileres_anual"
    )
    assert "mlops-annual-trainer" in all_json_str, (
        "El pipeline unificado debe invocar al Actor mlops-annual-trainer"
    )
    assert "WARN_GCBA_UNAVAILABLE" in all_json_str, (
        "El pipeline unificado debe incluir degradación elegante WARN_GCBA_UNAVAILABLE"
    )
