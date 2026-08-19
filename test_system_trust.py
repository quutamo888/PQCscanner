import pqc_probe


def test_openssl_command_keeps_handshake_on_external_ca_failure():
    command = pqc_probe.build_openssl_command(
        "example.com", 443, "X25519MLKEM768", ca_file="C:\\ca.pem"
    )
    assert "-verify_return_error" not in command


def test_python_trust_promotes_completed_handshake(monkeypatch):
    evidence = {
        "handshake_completed": True,
        "tls_version": "TLS 1.3",
        "certificate_trusted": False,
        "verification_status": "unverified",
        "transport_pqc": False,
    }
    monkeypatch.setattr(pqc_probe, "run_openssl_probe", lambda *args: evidence.copy())
    monkeypatch.setattr(pqc_probe, "inspect_x509_certificate", lambda *args: {
        "certificate_trusted": True,
        "is_pqc_cert": False,
        "signature_algorithm": "ecdsa-with-SHA256",
    })
    result = pqc_probe.scan_pqc("https://example.com")
    assert result["verification_status"] == "verified"
    assert result["certificate_trusted"] is True
