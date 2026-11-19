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
    assert search_node["parameters"].get("searchMethod") == "advanced"

    # 7. Purga a papelera con resource: file y operation: delete
    purge_node = nodes_by_name.get("Google Drive: Purgar Excedente a Papelera")
    assert purge_node is not None
    assert purge_node["parameters"].get("resource") == "file"
    assert purge_node["parameters"].get("operation") == "delete"



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
