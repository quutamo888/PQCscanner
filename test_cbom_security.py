from cbom_exporter import generate_cbom


def test_cbom_does_not_hardcode_classical_security_for_pqc():
    cbom = generate_cbom([{
        "host": "example.com",
        "url": "https://example.com",
        "verification_status": "verified",
        "transport_pqc": True,
        "key_exchange": {"group_name": "X25519MLKEM768", "is_pqc": True},
        "tls_info": {"version": "TLS 1.3"},
    }])
    asset = cbom["components"][1]
    props = asset["cryptoProperties"]["algorithmProperties"]
    assert props["classicalSecurityLevel"] is None
    assert props["nistQuantumSecurityLevel"] == 3
