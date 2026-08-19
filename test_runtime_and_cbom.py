import json
from pathlib import Path

from cbom_exporter import generate_cbom


def test_cbom_preserves_verification_and_standard_status():
    cbom = generate_cbom([{
        "url": "https://example.com",
        "host": "example.com",
        "passed": True,
        "grade": "A+",
        "verification_status": "verified",
        "transport_pqc": True,
        "transport_standard_status": "standard",
        "certificate_is_pqc": False,
        "certificate_trusted": True,
        "key_exchange": {
            "group_name": "X25519MLKEM768",
            "is_pqc": True,
            "group_hex": "0x11ec",
            "group_type": "Hybrid KEM",
            "group_standard": "ML-KEM-768 + X25519",
        },
        "tls_info": {"version": "TLS 1.3", "cipher_suite": "TLS_AES_128_GCM_SHA256"},
        "certificate": {"signature_algo": "ecdsa-with-SHA256", "subject": "CN=example.com"},
    }])
    service = cbom["components"][0]
    props = {p["name"]: p["value"] for p in service["properties"]}
    assert props["pqc:verification_status"] == "verified"
    assert props["pqc:transport_standard_status"] == "standard"
    assert props["pqc:certificate_trusted"] == "true"


def test_render_uses_platform_port():
    text = Path("render.yaml").read_text()
    assert "--port $PORT" in text


def test_run_script_checks_pqc_engine():
    text = Path("run.bat").read_text()
    assert "PQC_OPENSSL_PATH" in text
    assert "openssl version" in text
