"""Tests deterministas de validación de esquemas Apify (.actor/) y contratos de salida."""

import json
from pathlib import Path
import pytest

from actors.inference.src import main as inference_main

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTORS_DIR = REPO_ROOT / "actors"
INFERENCE_DIR = ACTORS_DIR / "inference"
TRAINER_DIR = ACTORS_DIR / "trainer"

OUTPUT_ALLOWED_PROP_KEYS = {"title", "type", "description", "template"}
DATASET_ALLOWED_ROOT_KEYS = {"$schema", "actorSpecification", "title", "description", "fields", "views"}


def _load_json(path: Path) -> dict:
    assert path.exists(), f"Archivo esperado no encontrado: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("actor_dir", [INFERENCE_DIR, TRAINER_DIR], ids=["inference", "trainer"])
def test_actor_manifest_and_referenced_files_exist(actor_dir: Path):
    """Verifica que actor.json referencie readme, input, output, storages y Dockerfile existentes."""
    actor_json_dir = actor_dir / ".actor"
    actor_cfg = _load_json(actor_json_dir / "actor.json")

    assert actor_cfg["actorSpecification"] == 1
    assert actor_cfg.get("name")
    assert actor_cfg.get("version")
    assert actor_cfg.get("actorPermissionLevel") == "LIMITED_PERMISSIONS"

    for key in ("dockerfile", "readme", "input", "output"):
        rel = actor_cfg.get(key)
        assert isinstance(rel, str) and rel, f"Falta '{key}' en {actor_json_dir / 'actor.json'}"
        resolved = (actor_json_dir / rel).resolve()
        assert resolved.exists(), f"Ruta referenciada '{key}' -> '{rel}' no existe ({resolved})"

    storages = actor_cfg.get("storages") or {}
    assert "dataset" in storages, "actor.json debe declarar storages.dataset"
    for storage_key, rel in storages.items():
        resolved = (actor_json_dir / rel).resolve()
        assert resolved.exists(), f"Ruta storage '{storage_key}' -> '{rel}' no existe ({resolved})"


@pytest.mark.parametrize("actor_dir", [INFERENCE_DIR, TRAINER_DIR], ids=["inference", "trainer"])
def test_actor_readme_meets_store_minimum_length(actor_dir: Path):
    """Verifica que cada Actor posea un README.md propio con al menos 300 palabras para Apify Store."""
    readme_path = actor_dir / "README.md"
    assert readme_path.exists(), f"Falta README.md en {actor_dir}"
    words = readme_path.read_text(encoding="utf-8").split()
    assert len(words) >= 300, f"{readme_path} tiene solo {len(words)} palabras (mínimo recomendado: 300)"


@pytest.mark.parametrize("actor_dir", [INFERENCE_DIR, TRAINER_DIR], ids=["inference", "trainer"])
def test_output_schema_conforms_to_apify_v1(actor_dir: Path):
    """Valida output_schema.json contra las reglas estrictas de https://apify.com/schemas/v1/output.json."""
    schema = _load_json(actor_dir / ".actor" / "output_schema.json")
    assert schema.get("actorOutputSchemaVersion") == 1
    props = schema.get("properties")
    assert isinstance(props, dict) and len(props) >= 1

    for prop_name, prop_def in props.items():
        assert isinstance(prop_def, dict)
        extra_keys = set(prop_def.keys()) - OUTPUT_ALLOWED_PROP_KEYS
        assert not extra_keys, f"Propiedad '{prop_name}' contiene claves no permitidas en output.json: {extra_keys}"
        assert prop_def.get("type") == "string", f"'{prop_name}.type' debe ser literalmente 'string'"
        template = prop_def.get("template")
        assert isinstance(template, str) and "{{links." in template, (
            f"'{prop_name}.template' debe usar interpolación '{{{{links.*}}}}'"
        )


@pytest.mark.parametrize("actor_dir", [INFERENCE_DIR, TRAINER_DIR], ids=["inference", "trainer"])
def test_dataset_schema_conforms_to_apify_v1(actor_dir: Path):
    """Valida dataset_schema.json contra https://apify.com/schemas/v1/dataset.json."""
    schema = _load_json(actor_dir / ".actor" / "dataset_schema.json")
    extra_root = set(schema.keys()) - DATASET_ALLOWED_ROOT_KEYS
    assert not extra_root, f"Claves raíz no permitidas en dataset_schema.json: {extra_root}"
    assert schema.get("actorSpecification") == 1

    fields = schema.get("fields") or {}
    assert fields.get("type") == "object"
    field_props = fields.get("properties") or {}
    assert len(field_props) >= 1

    views = schema.get("views") or {}
    assert len(views) >= 1
    for view_name, view_def in views.items():
        assert view_def.get("title")
        display = view_def.get("display") or {}
        assert display.get("component") in {"table", "grid"}
        view_fields = (view_def.get("transformation") or {}).get("fields") or []
        assert len(view_fields) >= 1, f"Vista '{view_name}' debe declarar transformation.fields"
        for col in view_fields:
            assert col in field_props, f"Campo '{col}' en vista '{view_name}' no existe en fields.properties"


def test_inference_dataset_schema_matches_runtime_pipeline_columns():
    """Verifica paridad exacta 1:1 entre las 30 columnas reales del pipeline y dataset_schema.json."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_zonaprop_raw.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        sample_raw = json.load(f)

    results = inference_main.run_pipeline(sample_raw[:3])
    assert len(results) == 3

    dataset_schema = _load_json(INFERENCE_DIR / ".actor" / "dataset_schema.json")
    schema_cols = set(dataset_schema["fields"]["properties"].keys())
    runtime_cols = set(results[0].keys())
    assert runtime_cols == schema_cols, (
        f"Desalineación entre runtime y dataset_schema.json. "
        f"Solo runtime: {runtime_cols - schema_cols}; solo schema: {schema_cols - runtime_cols}"
    )


def test_input_schemas_preserve_n8n_compatibility():
    """Verifica que los input_schema.json cubran los campos de n8n sin imponer required bloqueantes."""
    inf_input = _load_json(INFERENCE_DIR / ".actor" / "input_schema.json")
    assert inf_input.get("schemaVersion") == 1
    assert not inf_input.get("required")
    assert inf_input.get("additionalProperties") is not False
    for expected in ("datasetId", "properties", "limit", "modelStoreName", "modelKvStoreId"):
        assert expected in inf_input["properties"]
    # Verificación de delegación de permisos bajo LIMITED_PERMISSIONS (Store público sin tarjeta ni KYC)
    assert inf_input["properties"]["datasetId"].get("resourceType") == "dataset"
    assert inf_input["properties"]["datasetId"].get("resourcePermissions") == ["READ"]
    assert inf_input["properties"]["modelKvStoreId"].get("resourceType") == "keyValueStore"
    assert inf_input["properties"]["modelKvStoreId"].get("resourcePermissions") == ["READ"]

    trn_input = _load_json(TRAINER_DIR / ".actor" / "input_schema.json")
    assert trn_input.get("schemaVersion") == 1
    assert not trn_input.get("required")
    assert trn_input.get("additionalProperties") is not False
    for expected in (
        "gdriveFolderId",
        "minR2Threshold",
        "minSamples",
        "trainingData",
        "trainingDataCsvText",
        "trainingDataCsvUrl",
        "dataPath",
        "targetCol",
        "gdriveServiceAccountJson",
    ):
        assert expected in trn_input["properties"]
    assert trn_input["properties"]["trainingDataCsvText"]["type"] == ["string", "array"]


def test_trainer_kv_store_schema_conforms_to_apify_v1():
    """Valida key_value_store_schema.json del Actor Trainer contra el estándar oficial de Apify."""
    kv_schema = _load_json(TRAINER_DIR / ".actor" / "key_value_store_schema.json")
    assert kv_schema.get("actorKeyValueStoreSchemaVersion") == 1
    assert kv_schema.get("title")
    collections = kv_schema.get("collections") or {}
    assert len(collections) == 5

    keys_declared = set()
    for coll_name, coll in collections.items():
        assert coll.get("key") or coll.get("keyPrefix"), f"Colección '{coll_name}' sin key/keyPrefix"
        if coll.get("key"):
            keys_declared.add(coll["key"])
        content_types = coll.get("contentTypes") or []
        assert len(content_types) >= 1
        if "jsonSchema" in coll:
            assert content_types == ["application/json"], (
                f"Colección '{coll_name}' con jsonSchema debe declarar contentTypes=['application/json']"
            )

    assert keys_declared == {
        "OUTPUT",
        "models_manifest.json",
        "kmeans_model.joblib",
        "xgb_price_model.joblib",
        "model_metadata.joblib",
    }
