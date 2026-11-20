"""Deterministic verification suite for the Executive Analytics Showcase Notebook."""
import json
from pathlib import Path

NOTEBOOK_PATH = Path("notebooks/observatorio_caba_showcase.ipynb")
FORBIDDEN_IMPORTS = ("plotly", "folium", "shap", "statsmodels")


def test_showcase_notebook_exists_and_valid_schema():
    """Verifies notebook exists, is valid nbformat v4 JSON, and has zero forbidden dependencies."""
    assert NOTEBOOK_PATH.exists(), f"Missing showcase notebook at {NOTEBOOK_PATH}"
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    assert nb.get("nbformat") == 4
    cells = nb.get("cells", [])
    assert len(cells) >= 12, f"Expected >= 12 cells, found {len(cells)}"

    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    assert len(code_cells) >= 6

    all_code = "\n".join("".join(c.get("source", [])) for c in code_cells)
    for forbidden in FORBIDDEN_IMPORTS:
        assert f"import {forbidden}" not in all_code, f"Forbidden import '{forbidden}' found"
        assert f"from {forbidden}" not in all_code, f"Forbidden import '{forbidden}' found"


def test_showcase_notebook_covers_business_questions_and_outputs():
    """Verifies coverage of Q1-Q5, H1-H6, crime volume/gravity, K-Means, XGBoost+TreeSHAP, Registry v1, and >=6 PNG outputs."""
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = nb.get("cells", [])

    full_text = "\n".join("".join(c.get("source", [])) for c in cells)
    for token in (
        "Q1", "Q2", "Q3", "Q4", "Q5",
        "H1", "H2", "H3", "H4", "H5", "H6",
        "densidad_delitos_500m",
        "indice_gravedad_delitos_500m",
        "K-Means",
        "XGBoost",
        "pred_contribs",
        "registry.json",
    ):
        assert token in full_text, f"Expected analytical topic '{token}' in showcase notebook"

    # Count embedded PNG outputs and verify zero cell execution errors
    png_count = 0
    for idx, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        outputs = cell.get("outputs", [])
        for out in outputs:
            assert out.get("output_type") != "error", f"Cell {idx} has execution error: {out.get('evalue')}"
            data = out.get("data", {})
            if "image/png" in data:
                png_count += 1

    assert png_count >= 6, f"Expected >= 6 embedded PNG figures, found {png_count}"
