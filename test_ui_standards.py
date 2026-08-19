from pathlib import Path


def test_ui_does_not_claim_quantum_proof():
    text = Path("static/app.js").read_text()
    assert "Quantum Proof" not in text
    assert "PQC Transport Verified" in text


def test_ui_renders_verification_status():
    text = Path("static/app.js").read_text()
    assert "verification_status" in text
    assert "engine_unavailable" in text
