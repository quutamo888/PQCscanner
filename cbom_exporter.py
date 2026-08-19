import uuid
import datetime
from typing import List, Dict, Any

def generate_cbom(scan_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bom_uuid = str(uuid.uuid4())

    components = []
    dependencies = []

    for idx, item in enumerate(scan_results):
        host = item.get("host") or item.get("url") or f"asset-{idx}"
        url = item.get("url") or f"https://{host}"
        passed = item.get("passed", False)
        grade = item.get("grade", "U")
        kex = item.get("key_exchange") or {}
        tls = item.get("tls_info") or {}
        cert = item.get("certificate") or {}

        service_ref = f"service-{host}-{idx}"
        kex_ref = f"crypto-kex-{host}-{idx}"
        proto_ref = f"crypto-proto-{host}-{idx}"
        cert_ref = f"crypto-cert-{host}-{idx}"

        asset_refs = []

        # 1. Main Service / Endpoint Component
        service_comp = {
            "type": "service",
            "bom-ref": service_ref,
            "name": host,
            "endpoints": [url],
            "properties": [
                {"name": "pqc:status", "value": "PASSED" if passed else "FAILED"},
                {"name": "pqc:grade", "value": grade},
                {"name": "pqc:verification_status", "value": item.get("verification_status", "unknown")},
                {"name": "pqc:engine_version", "value": (item.get("evidence") or {}).get("engine_version", "unknown")},
                {"name": "pqc:transport_pqc", "value": str(item.get("transport_pqc")).lower()},
                {"name": "pqc:transport_standard_status", "value": item.get("transport_standard_status", "unknown")},
                {"name": "pqc:certificate_is_pqc", "value": str(item.get("certificate_is_pqc", cert.get("is_pqc", False))).lower()},
                {"name": "pqc:certificate_trusted", "value": str(item.get("certificate_trusted", False)).lower()},
                {"name": "pqc:overall_readiness", "value": item.get("overall_readiness", "unknown")},
                {"name": "pqc:status_title", "value": item.get("status_title", "")},
                {"name": "pqc:reason_th", "value": item.get("reason_th", "")},
                {"name": "pqc:reason_en", "value": item.get("reason_en", "")},
                {"name": "pqc:latency_ms", "value": str(item.get("latency_ms", 0))}
            ]
        }
        components.append(service_comp)

        # 2. Cryptographic Asset: Key Exchange / KEM Algorithm
        if kex.get("group_name"):
            is_pqc_kex = kex.get("is_pqc", False)
            q_level = 0
            if "768" in kex.get("group_name", ""):
                q_level = 3
            elif "512" in kex.get("group_name", ""):
                q_level = 1
            elif "1024" in kex.get("group_name", ""):
                q_level = 5

            kex_comp = {
                "type": "cryptographic-asset",
                "bom-ref": kex_ref,
                "name": kex.get("group_name"),
                "description": f"Key Encapsulation / Exchange Mechanism for {host}",
                "cryptoProperties": {
                    "assetType": "algorithm",
                    "algorithmProperties": {
                        "primitive": "kem" if is_pqc_kex else "key-exchange",
                        "parameterSetIdentifier": kex.get("group_name"),
                        "executionEnvironment": "tls-handshake",
                        "cryptoFunctions": ["key-encapsulation", "key-agreement"],
                        "classicalSecurityLevel": None if is_pqc_kex else 128,
                        "nistQuantumSecurityLevel": q_level
                    },
                    "oid": kex.get("group_hex", "")
                },
                "properties": [
                    {"name": "pqc:is_quantum_resistant", "value": "true" if is_pqc_kex else "false"},
                    {"name": "pqc:group_type", "value": kex.get("group_type", "")},
                    {"name": "pqc:standard", "value": kex.get("group_standard", "")}
                ]
            }
            components.append(kex_comp)
            asset_refs.append(kex_ref)

        # 3. Cryptographic Asset: TLS Protocol & Cipher Suite
        if tls.get("version"):
            proto_comp = {
                "type": "cryptographic-asset",
                "bom-ref": proto_ref,
                "name": f"{tls.get('version')} Protocol",
                "cryptoProperties": {
                    "assetType": "protocol",
                    "protocolProperties": {
                        "type": "tls",
                        "version": tls.get("version", ""),
                        "cipherSuites": [
                            {
                                "name": tls.get("cipher_suite", ""),
                                "algorithms": [tls.get("cipher_suite", "")]
                            }
                        ]
                    }
                }
            }
            components.append(proto_comp)
            asset_refs.append(proto_ref)

        # 4. Cryptographic Asset: X.509 Certificate
        if cert.get("signature_algo") or cert.get("subject"):
            cert_comp = {
                "type": "cryptographic-asset",
                "bom-ref": cert_ref,
                "name": f"{host} Public Key Certificate",
                "cryptoProperties": {
                    "assetType": "certificate",
                    "certificateProperties": {
                        "subjectName": cert.get("subject", ""),
                        "issuerName": cert.get("issuer", ""),
                        "notValidBefore": cert.get("valid_from", ""),
                        "notValidAfter": cert.get("valid_until", ""),
                        "signatureAlgorithmRef": cert.get("signature_algo", ""),
                        "subjectPublicKeyAlgorithm": cert.get("public_key_type", ""),
                        "fingerprint": cert.get("fingerprint_sha256", "")
                    }
                },
                "properties": [
                    {"name": "pqc:certificate_is_pqc", "value": "true" if cert.get("is_pqc") else "false"},
                    {"name": "pqc:public_key_size_bits", "value": str(cert.get("key_size", ""))}
                ]
            }
            components.append(cert_comp)
            asset_refs.append(cert_ref)

        # Dependency map
        dependencies.append({
            "ref": service_ref,
            "dependsOn": asset_refs
        })

    cbom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{bom_uuid}",
        "version": 1,
        "metadata": {
            "timestamp": now_iso,
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "PQC Compliance Scanner",
                        "version": "1.0.0",
                        "description": "Post-Quantum Cryptography Readiness & TLS 1.3 Key Exchange Analyzer"
                    }
                ]
            },
            "component": {
                "type": "application",
                "name": "Cryptographic Inventory (CBOM)",
                "description": "Inventory of Cryptographic Assets, PQC Hybrid KEM Algorithms, and TLS Parameters"
            }
        },
        "components": components,
        "dependencies": dependencies
    }

    return cbom
