"""
Pruebas Automatizadas de la Opción B2 (Entrega Continua con Controles de Calidad — Escenario EC-12 y ADR-14).
Verifica:
1. Que el Quality Gate bloquea la promoción en el 100 % de los casos cuando se introduce una prueba rota
   (`test_failure`), un hallazgo crítico de análisis estático (`static_finding`) o un secreto expuesto.
2. Que el repositorio actual cumple la política de secretos fuera del repositorio (`0` llaves o tokens hardcodeados).
3. Que el pipeline definido como código (`.github/workflows/ci-cd-quality-gate.yml`), la prueba de humo en Staging
   (`tests/load/k6_smoke_staging.js`) y el procedimiento ejecutable de reversión (`deploy/scripts/rollback_release.sh`)
   contienen todas las etapas exigidas por el mínimo de B2.
"""

from pathlib import Path

from deploy.scripts.quality_gate_runner import (
    BASE_DIR,
    evaluate_quality_gate,
    scan_repository_for_hardcoded_secrets,
)


def test_ec12_quality_gate_blocks_100_percent_on_test_failure_or_static_finding() -> None:
    """
    Escenario EC-12: Un integrante incorpora a la rama principal un cambio que rompe una prueba
    o introduce un hallazgo crítico -> El pipeline bloquea la promoción en el 100 % de los casos.
    """
    report_test_fail = evaluate_quality_gate(simulate_defect="test_failure", run_subprocesses=False)
    assert report_test_fail.all_passed is False
    assert report_test_fail.blocked_promotion is True

    report_static_fail = evaluate_quality_gate(simulate_defect="static_finding", run_subprocesses=False)
    assert report_static_fail.all_passed is False
    assert report_static_fail.blocked_promotion is True


def test_ec12_secret_scanner_detects_exposed_credentials_and_approves_clean_repo(tmp_path: Path) -> None:
    """Verifica que los secretos se gestionen fuera del repositorio y que el escáner bloquee llaves expuestas."""
    # 1. El repositorio real no debe tener secretos expuestos
    real_scan = scan_repository_for_hardcoded_secrets(BASE_DIR)
    assert real_scan.passed is True

    # 2. Si alguien intenta subir un archivo con una llave privada o token GitHub, el escáner lo bloquea
    bad_file = tmp_path / "leaked_config.py"
    synthetic_token = "ghp_" + ("a" * 34)
    bad_file.write_text(f'TOKEN = "{synthetic_token}"\n', encoding="utf-8")
    leaked_scan = scan_repository_for_hardcoded_secrets(tmp_path)
    assert leaked_scan.passed is False
    assert "leaked_config.py" in leaked_scan.details


def test_b2_pipeline_and_operational_artifacts_exist_and_include_required_controls() -> None:
    """Verifica la presencia e integridad del pipeline CI/CD, Trivy, k6 smoke test y script de rollback."""
    workflow_path = BASE_DIR / ".github" / "workflows" / "ci-cd-quality-gate.yml"
    k6_smoke_path = BASE_DIR / "tests" / "load" / "k6_smoke_staging.js"
    rollback_path = BASE_DIR / "deploy" / "scripts" / "rollback_release.sh"

    assert workflow_path.exists()
    assert k6_smoke_path.exists()
    assert rollback_path.exists()

    workflow_text = workflow_path.read_text(encoding="utf-8")
    assert "quality_gate_runner.py" in workflow_text
    assert "aquasecurity/trivy-action" in workflow_text
    assert "k6_smoke_staging.js" in workflow_text
    assert "promote-to-production" in workflow_text
    assert "secrets." in workflow_text

    k6_text = k6_smoke_path.read_text(encoding="utf-8")
    assert "/api/v1/products/" in k6_text
    assert "/price-history/?days=90" in k6_text

    rollback_text = rollback_path.read_text(encoding="utf-8")
    assert "previous-stable" in rollback_text
    assert "--dry-run" in rollback_text
