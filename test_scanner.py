from pqc_probe import parse_target, build_client_hello, scan_pqc
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_parse_target():
    host, port = parse_target("https://example.com")
    assert host == "example.com"
    assert port == 443

    host, port = parse_target("http://test.local:8080")
    assert host == "test.local"
    assert port == 8080

    host, port = parse_target("pq.cloudflareresearch.com")
    assert host == "pq.cloudflareresearch.com"
    assert port == 443

def test_build_client_hello():
    record = build_client_hello("cloudflare.com")
    assert len(record) > 50
    assert record[0] == 22 # Handshake
    assert record[1:3] == b'\x03\x01' # TLS 1.0 record version

def test_scan_pqc_detection():
    # Test PQC site (Cloudflare or Google)
    res_pqc = scan_pqc("https://cloudflare.com", timeout=5.0)
    print("Cloudflare scan result:", res_pqc)
    assert res_pqc["host"] == "cloudflare.com"
    assert res_pqc["passed"] is True
    assert res_pqc["key_exchange"]["is_pqc"] is True
    assert "ผ่าน" in res_pqc["status_title"]
    assert len(res_pqc["reason_th"]) > 0

    # Test Classical site (GitHub)
    res_classical = scan_pqc("https://github.com", timeout=5.0)
    assert res_classical["host"] == "github.com"
    assert res_classical["passed"] is False
    assert res_classical["key_exchange"]["is_pqc"] is False
    assert "ยังไม่ผ่าน" in res_classical["status_title"]
    assert len(res_classical["reason_th"]) > 0

def test_fastapi_endpoints():
    # Test presets
    res = client.get("/api/presets")
    assert res.status_code == 200
    presets = res.json()
    assert len(presets) > 0

    # Test single scan endpoint
    res_scan = client.post("/api/scan", json={"url": "https://cloudflare.com", "timeout": 5.0})
    assert res_scan.status_code == 200
    data = res_scan.json()
    assert data["passed"] is True
    assert "reason_th" in data

if __name__ == "__main__":
    print("Running tests...")
    test_parse_target()
    print("test_parse_target passed!")
    test_build_client_hello()
    print("test_build_client_hello passed!")
    test_scan_pqc_detection()
    print("test_scan_pqc_detection passed!")
    test_fastapi_endpoints()
    print("test_fastapi_endpoints passed!")
    print("ALL TESTS PASSED SUCCESSFULLY!")
