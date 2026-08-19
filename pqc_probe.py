import socket
import ssl
import struct
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# TLS supported-group registry. Status follows current IANA/RFC references.
PQC_GROUPS = {
    0x11ec: {
        "name": "X25519MLKEM768",
        "type": "Hybrid KEM",
        "standard": "ML-KEM-768 + X25519",
        "reference": "RFC 10024",
        "standard_status": "standard",
        "is_pqc": True,
        "desc": "Post-Quantum Hybrid (X25519 ECDH + NIST ML-KEM-768)"
    },
    0x11eb: {
        "name": "SecP256r1MLKEM768",
        "type": "Hybrid KEM",
        "standard": "ML-KEM-768 + secp256r1",
        "reference": "RFC 10024",
        "standard_status": "standard",
        "is_pqc": True,
        "desc": "Post-Quantum Hybrid (secp256r1 ECDH + NIST ML-KEM-768)"
    },
    0x0200: {
        "name": "MLKEM512",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203",
        "reference": "IANA TLS Supported Groups",
        "standard_status": "draft",
        "is_pqc": False,
        "desc": "FIPS 203 ML-KEM-512 TLS named group is not yet standards-track"
    },
    0x0201: {
        "name": "MLKEM768",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203",
        "reference": "IANA TLS Supported Groups",
        "standard_status": "draft",
        "is_pqc": False,
        "desc": "FIPS 203 ML-KEM-768 TLS named group is not yet standards-track"
    },
    0x0202: {
        "name": "MLKEM1024",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203",
        "reference": "IANA TLS Supported Groups",
        "standard_status": "draft",
        "is_pqc": False,
        "desc": "FIPS 203 ML-KEM-1024 TLS named group is not yet standards-track"
    },
    0x6399: {
        "name": "x25519_kyber768draft00",
        "type": "Hybrid KEM",
        "standard": "Kyber Round 3 Draft00",
        "reference": "IETF draft",
        "standard_status": "draft",
        "is_pqc": False,
        "desc": "Legacy experimental hybrid group"
    },
    0x45ac: {
        "name": "secp256r1_kyber768draft00",
        "type": "Hybrid KEM",
        "standard": "Kyber Round 3 Draft00",
        "reference": "IETF draft",
        "standard_status": "draft",
        "is_pqc": False,
        "desc": "Legacy experimental hybrid group"
    },
    0x639a: {
        "name": "x25519_bikel1",
        "type": "Hybrid KEM",
        "standard": "BIKE Round 4",
        "reference": "IETF draft",
        "standard_status": "experimental",
        "is_pqc": False,
        "desc": "Experimental BIKE hybrid group"
    },
    0x639b: {
        "name": "x25519_hqc128",
        "type": "Hybrid KEM",
        "standard": "HQC Round 4",
        "reference": "IETF draft",
        "standard_status": "experimental",
        "is_pqc": False,
        "desc": "Experimental HQC hybrid group"
    }
}


def get_group_info(group_id: int) -> Dict[str, Any]:
    """Return normalized group metadata; unknown IDs stay explicitly unknown."""
    if group_id in PQC_GROUPS:
        return dict(PQC_GROUPS[group_id])
    if group_id in CLASSICAL_GROUPS:
        info = dict(CLASSICAL_GROUPS[group_id])
        info.update({
            "type": "Classical ECDH",
            "reference": "RFC 8446",
            "standard_status": "standard",
            "is_pqc": False,
        })
        return info
    return {
        "name": f"Unknown Group (0x{group_id:04x})",
        "type": "Unknown",
        "reference": "",
        "standard_status": "unknown",
        "is_pqc": False,
        "desc": "Unrecognized TLS supported group",
    }

CIPHER_SUITES = {
    0x1301: "TLS_AES_128_GCM_SHA256",
    0x1302: "TLS_AES_256_GCM_SHA384",
    0x1303: "TLS_CHACHA20_POLY1305_SHA256",
    0xc02f: "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    0xc030: "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    0xc02b: "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    0xc02c: "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    0xcca8: "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
    0xcca9: "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
}

# HRR magic random bytes (RFC 8446)
HRR_RANDOM = b'\xcf!\xadtno\x06\xe0\x0e\xea\x9f\x1fe\x1eQ>\x01B\x90e\x86\x85\x10\xb2\xe0\xce\xddap[\x0f\x88'

def parse_target(target: str) -> Tuple[str, int]:
    """Parse raw URL or host:port into host and port."""
    target = target.strip()
    if not target:
        raise ValueError("URL หรือ Hostname ไม่สามารถเป็นค่าว่างได้")
    
    if "://" not in target:
        target = "https://" + target
        
    parsed = urllib.parse.urlparse(target)
    host = parsed.hostname or parsed.netloc.split(":")[0]
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    
    if not host:
        raise ValueError(f"ไม่สามารถอ่าน Hostname จาก: {target}")
        
    return host, port

def build_client_hello(host: str) -> bytes:
    """Craft TLS 1.3 ClientHello with PQC groups, ALPN, PSK modes, and dual key shares."""
    client_random = os.urandom(32)
    session_id = os.urandom(32)
    
    # 1. Server Name Indication (SNI) - 0x0000
    host_bytes = host.encode('utf-8')
    sni_data = struct.pack("!HB", len(host_bytes) + 3, 0) + struct.pack("!H", len(host_bytes)) + host_bytes
    ext_sni = struct.pack("!HH", 0x0000, len(sni_data)) + sni_data
    
    # 2. Supported Versions - 0x002b (TLS 1.3 = 0x0304, TLS 1.2 = 0x0303)
    sup_versions = struct.pack("!BHH", 4, 0x0304, 0x0303)
    ext_sup_versions = struct.pack("!HH", 0x002b, len(sup_versions)) + sup_versions
    
    # 3. Supported Groups - 0x000a (Offer PQC Hybrid first, then Pure PQC, then Classical)
    groups = [
        0x11ec, # X25519MLKEM768 (NIST standard)
        0x6399, # x25519_kyber768draft00 (Cloudflare/Google Kyber)
        0x45ac, # secp256r1_kyber768draft00
        0x11eb, # SecP256r1MLKEM768
        0x0201, # ML-KEM-768
        0x0200, # ML-KEM-512
        0x0202, # ML-KEM-1024
        0x001d, # x25519
        0x0017, # secp256r1
        0x0018  # secp384r1
    ]
    groups_body = b''.join(struct.pack("!H", g) for g in groups)
    groups_data = struct.pack("!H", len(groups_body)) + groups_body
    ext_sup_groups = struct.pack("!HH", 0x000a, len(groups_data)) + groups_data
    
    # 4. ALPN (0x0010) -> h2, http/1.1 (Required by modern WAFs/Cloudflare)
    alpn_list = b'\x02h2\x08http/1.1'
    alpn_data = struct.pack("!H", len(alpn_list)) + alpn_list
    ext_alpn = struct.pack("!HH", 0x0010, len(alpn_data)) + alpn_data

    # 5. PSK Key Exchange Modes (0x002d) -> psk_dhe_ke (1)
    psk_modes = struct.pack("!BB", 1, 1)
    ext_psk_modes = struct.pack("!HH", 0x002d, len(psk_modes)) + psk_modes

    # 6. EC Point Formats (0x000b) -> uncompressed (0)
    ec_formats = struct.pack("!BB", 1, 0)
    ext_ec_formats = struct.pack("!HH", 0x000b, len(ec_formats)) + ec_formats

    # 7. Signature Algorithms - 0x000d (RSA-PSS, ECDSA, RSA-PKCS1)
    sig_algos = [0x0804, 0x0403, 0x0805, 0x0503, 0x0806, 0x0603, 0x0401, 0x0501, 0x0601]
    sig_body = b''.join(struct.pack("!H", s) for s in sig_algos)
    sig_data = struct.pack("!H", len(sig_body)) + sig_body
    ext_sig = struct.pack("!HH", 0x000d, len(sig_data)) + sig_data
    
    # 8. Key Share - 0x0033 (Dual: x25519 + secp256r1)
    x25519_pk = b'\x09' + b'\x00' * 31
    ks_001d = struct.pack("!HH", 0x001d, 32) + x25519_pk
    p256_pk = bytes.fromhex("046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
    ks_0017 = struct.pack("!HH", 0x0017, 65) + p256_pk
    ks_data_body = ks_001d + ks_0017
    ks_data = struct.pack("!H", len(ks_data_body)) + ks_data_body
    ext_ks = struct.pack("!HH", 0x0033, len(ks_data)) + ks_data
    
    # Combine all extensions
    all_extensions = ext_sni + ext_sup_versions + ext_sup_groups + ext_psk_modes + ext_ec_formats + ext_sig + ext_alpn + ext_ks
    ext_total = struct.pack("!H", len(all_extensions)) + all_extensions
    
    # Cipher suites (TLS 1.3 AES-GCM & ChaCha, TLS 1.2 ECDHE)
    ciphers = [0x1301, 0x1302, 0x1303, 0xc02f, 0xc030, 0xc02b, 0xc02c, 0xcca8, 0xcca9]
    cipher_bytes = struct.pack("!H", len(ciphers) * 2) + b''.join(struct.pack("!H", c) for c in ciphers)
    
    # Compression (0 = null)
    comp = b'\x01\x00'
    
    # ClientHello body
    ch_body = (
        struct.pack("!H", 0x0303) + # Legacy version
        client_random +
        struct.pack("!B", len(session_id)) + session_id +
        cipher_bytes +
        comp +
        ext_total
    )
    
    # Handshake header (Type 1 = ClientHello)
    hs_header = struct.pack("!B", 1) + struct.pack("!I", len(ch_body))[1:]
    hs_msg = hs_header + ch_body
    
    # Record header (Type 22 = Handshake, TLS 1.0 legacy version 0x0301)
    record = struct.pack("!BHH", 22, 0x0301, len(hs_msg)) + hs_msg
    return record

def parse_server_hello(resp: bytes) -> Dict[str, Any]:
    """Parse ServerHello or HelloRetryRequest handshake message."""
    if len(resp) < 4:
        raise ValueError("Server response too short")
        
    hs_type = resp[0]
    if hs_type != 2:
        raise ValueError(f"Expected ServerHello (type 2), got type {hs_type}")
        
    if len(resp) < 38:
        raise ValueError("Truncated ServerHello header")
        
    server_random = resp[6:38]
    is_hrr = (server_random == HRR_RANDOM)
    
    idx = 38
    sess_id_len = resp[idx]
    idx += 1 + sess_id_len
    
    if len(resp) < idx + 3:
        raise ValueError("Truncated ServerHello cipher/compression")
        
    selected_cipher = struct.unpack("!H", resp[idx:idx+2])[0]
    idx += 2 + 1 # Skip cipher (2) + comp (1)
    
    selected_group = None
    supported_version = None
    
    if len(resp) >= idx + 2:
        ext_len = struct.unpack("!H", resp[idx:idx+2])[0]
        idx += 2
        ext_end = idx + ext_len
        
        while idx + 4 <= ext_end and idx + 4 <= len(resp):
            ext_type, e_len = struct.unpack("!HH", resp[idx:idx+4])
            idx += 4
            e_data = resp[idx:idx+e_len]
            idx += e_len
            
            if ext_type == 0x002b: # supported_versions
                if len(e_data) >= 2:
                    supported_version = struct.unpack("!H", e_data[:2])[0]
            elif ext_type == 0x0033: # key_share
                if len(e_data) >= 2:
                    selected_group = struct.unpack("!H", e_data[:2])[0]
                    
    return {
        "is_hrr": is_hrr,
        "selected_cipher_id": selected_cipher,
        "cipher_name": CIPHER_SUITES.get(selected_cipher, f"0x{selected_cipher:04x}"),
        "supported_version": supported_version,
        "selected_group_id": selected_group,
    }

def build_verified_context(host: str) -> ssl.SSLContext:
    """Create a system-trust TLS context with hostname verification enabled."""
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def inspect_x509_certificate(host: str, port: int = 443, timeout: float = 4.0) -> Dict[str, Any]:
    """Retrieve and inspect a trusted X.509 server certificate."""
    ctx = build_verified_context(host)

    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            der_cert = ssock.getpeercert(binary_form=True)
            tls_ver = ssock.version()
            tls_cipher = ssock.cipher()

            cert = x509.load_der_x509_certificate(der_cert, default_backend())
            sig_algo = cert.signature_algorithm_oid._name
            pub_key = cert.public_key()
            pub_type = pub_key.__class__.__name__
            issuer = cert.issuer.rfc4514_string()
            subject = cert.subject.rfc4514_string()
            not_after = cert.not_valid_after_utc.isoformat()
            not_before = cert.not_valid_before_utc.isoformat()

            sans = []
            try:
                san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                sans = san_ext.value.get_values_for_type(x509.DNSName)
            except x509.ExtensionNotFound:
                pass

            is_pqc_sig = any(pqc in sig_algo.lower() for pqc in [
                "dilithium", "mldsa", "ml-dsa", "falcon", "sphincs", "xmss", "slh-dsa"
            ])

            return {
                "tls_version": tls_ver,
                "tls_cipher": tls_cipher[0] if tls_cipher else None,
                "subject": subject,
                "issuer": issuer,
                "signature_algorithm": sig_algo,
                "public_key_type": pub_type,
                "valid_from": not_before,
                "valid_until": not_after,
                "sans": sans[:5],
                "is_pqc_cert": is_pqc_sig,
                "certificate_trusted": True,
                "hostname_valid": True,
                "validity_valid": True,
            }


def find_openssl() -> Optional[str]:
    """Find explicitly configured or PATH-provided OpenSSL executable."""
    configured = os.environ.get("PQC_OPENSSL_PATH")
    if configured and os.path.isfile(configured):
        return configured
    return shutil.which("openssl")


def get_openssl_version(executable: str) -> Optional[str]:
    try:
        completed = subprocess.run(
            [executable, "version"], capture_output=True, text=True,
            timeout=3.0, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr or "").strip() or None


def _openssl_version_supports_pqc(version_text: Optional[str]) -> bool:
    match = re.search(r"OpenSSL\s+(\d+)\.(\d+)\.(\d+)", version_text or "")
    return bool(match and (int(match.group(1)), int(match.group(2))) >= (3, 5))


def openssl_supports_pqc(executable: str) -> bool:
    """Return true only for OpenSSL versions with the required PQC groups."""
    return _openssl_version_supports_pqc(get_openssl_version(executable))


def build_openssl_command(host: str, port: int, group: str, timeout: float = 4.0) -> list[str]:
    """Build a TLS 1.3 probe command with one selected supported group."""
    return [
        "openssl", "s_client",
        "-connect", f"{host}:{port}",
        "-servername", host,
        "-verify_hostname", host,
        "-verify_return_error",
        "-tls1_3",
        "-groups", group,
        "-brief",
        "-no_ticket",
        "-ign_eof",
    ]


def parse_openssl_result(completed: subprocess.CompletedProcess) -> Dict[str, Any]:
    """Parse only completed TLS 1.3 evidence; never infer PQC from advertisements."""
    text = f"{completed.stdout or ''}\n{completed.stderr or ''}"
    tls_match = re.search(r"Protocol version:\s*TLSv?([0-9.]+)", text, re.I)
    cipher_match = re.search(r"Ciphersuite:\s*([^\s]+)", text, re.I)
    group_match = re.search(r"(?:Negotiated TLS1\.3 group|Server Temp Key):\s*([^\s,]+)", text, re.I)
    handshake_output = bool(re.search(
        r"SSL handshake has read\s+\d+ bytes and written\s+\d+ bytes",
        text, re.I,
    )) or bool(re.search(r"CONNECTION ESTABLISHED.*\bDONE\b", text, re.I | re.S))
    handshake_completed = (
        completed.returncode == 0
        and handshake_output
        and tls_match is not None
        and tls_match.group(1) == "1.3"
    )
    certificate_trusted = bool(re.search(r"Verification:\s*OK", text, re.I))
    group = group_match.group(1) if group_match else None
    transport_pqc = group in {"X25519MLKEM768", "SecP256r1MLKEM768"}
    if handshake_completed and certificate_trusted:
        verification_status = "verified"
    elif completed.returncode != 0:
        verification_status = "error"
    else:
        verification_status = "unverified"
    return {
        "handshake_completed": handshake_completed,
        "tls_version": f"TLS {tls_match.group(1)}" if tls_match else "Unknown",
        "cipher_suite": cipher_match.group(1) if cipher_match else "Unknown",
        "selected_group": group,
        "certificate_trusted": certificate_trusted,
        "transport_pqc": transport_pqc if group else False,
        "verification_status": verification_status,
        "error": (completed.stderr or "").strip() or None,
    }


def run_openssl_probe(host: str, port: int, timeout: float = 4.0) -> Dict[str, Any]:
    """Probe standard hybrid and classical groups using configured OpenSSL."""
    executable = find_openssl()
    engine_version = get_openssl_version(executable) if executable else None
    if not executable or not _openssl_version_supports_pqc(engine_version):
        return {
            "handshake_completed": False,
            "certificate_trusted": False,
            "transport_pqc": None,
            "verification_status": "engine_unavailable",
            "engine_version": engine_version,
            "error": "OpenSSL 3.5+ PQC engine unavailable",
        }
    command = build_openssl_command(host, port, "X25519MLKEM768:X25519:secp256r1", timeout)
    command[0] = executable
    try:
        completed = subprocess.run(
            command, input="", capture_output=True, text=True,
            timeout=max(1.0, timeout + 1.0), check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "handshake_completed": False,
            "certificate_trusted": False,
            "transport_pqc": False,
            "verification_status": "error",
            "engine_version": engine_version,
            "error": str(exc),
        }
    evidence = parse_openssl_result(completed)
    evidence["engine_version"] = engine_version
    return evidence


def scan_pqc(target_url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """Run a standards-aware TLS 1.3 PQC readiness scan."""
    start_time = time.time()
    result = {
        "url": target_url,
        "host": "",
        "port": 443,
        "passed": False,
        "grade": "F",
        "status_badge": "error",
        "status_title": "เกิดข้อผิดพลาด",
        "status_title_en": "Error",
        "reason_th": "",
        "reason_en": "",
        "transport_pqc": None,
        "transport_standard_status": "unknown",
        "certificate_is_pqc": False,
        "certificate_trusted": False,
        "overall_readiness": "unknown",
        "verification_status": "unknown",
        "evidence": {},
        "key_exchange": {
            "is_pqc": False,
            "group_id": None,
            "group_hex": None,
            "group_name": "None",
            "group_type": "None",
            "group_standard": "None",
            "details": "None"
        },
        "certificate": {
            "is_pqc": False,
            "signature_algo": "Unknown",
            "public_key_type": "Unknown",
            "issuer": "Unknown",
            "subject": "Unknown",
            "valid_until": "Unknown"
        },
        "tls_info": {
            "version": "Unknown",
            "cipher_suite": "Unknown",
            "handshake_type": "OpenSSL s_client"
        },
        "latency_ms": 0,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "error": None
    }

    try:
        host, port = parse_target(target_url)
        result["host"] = host
        result["port"] = port
        evidence = run_openssl_probe(host, port, timeout)
        result["evidence"] = evidence
        result["verification_status"] = evidence["verification_status"]
        result["transport_pqc"] = evidence["transport_pqc"]
        result["certificate_trusted"] = evidence.get("certificate_trusted", False)
        result["tls_info"]["version"] = evidence.get("tls_version", "Unknown")
        result["tls_info"]["cipher_suite"] = evidence.get("cipher_suite", "Unknown")

        if evidence["verification_status"] == "engine_unavailable":
            result["error"] = evidence["error"]
            result["status_title"] = "ไม่สามารถยืนยัน PQC ได้"
            result["status_title_en"] = "PQC Verification Unavailable"
            result["reason_th"] = "ไม่พบ OpenSSL 3.5+ PQC engine จึงไม่รายงานผล PQC แบบยืนยัน"
            result["reason_en"] = "OpenSSL 3.5+ PQC engine is unavailable; PQC result is not verified."
            result["latency_ms"] = round((time.time() - start_time) * 1000, 1)
            return result

        selected_group = evidence.get("selected_group")
        if selected_group:
            group_id = next(
                (gid for gid, info in PQC_GROUPS.items()
                 if info["name"].lower() == selected_group.lower()),
                None,
            )
            if group_id is not None:
                info = get_group_info(group_id)
                result["key_exchange"].update({
                    "group_id": group_id,
                    "group_hex": f"0x{group_id:04x}",
                    "group_name": info["name"],
                    "group_type": info["type"],
                    "group_standard": info.get("standard", ""),
                    "details": info.get("desc", ""),
                })
                result["transport_standard_status"] = info["standard_status"]
                result["key_exchange"]["is_pqc"] = bool(
                    evidence["transport_pqc"] and info["standard_status"] == "standard"
                )

        try:
            cert_info = inspect_x509_certificate(host, port, timeout)
        except (OSError, ssl.SSLError, ValueError) as cert_error:
            cert_info = {"error": str(cert_error), "certificate_trusted": False}
        if "error" not in cert_info:
            result["certificate"].update({
                "signature_algo": cert_info.get("signature_algorithm", "Unknown"),
                "public_key_type": cert_info.get("public_key_type", "Unknown"),
                "issuer": cert_info.get("issuer", "Unknown"),
                "subject": cert_info.get("subject", "Unknown"),
                "valid_until": cert_info.get("valid_until", "Unknown"),
                "is_pqc": cert_info.get("is_pqc_cert", False),
            })
            result["certificate_is_pqc"] = cert_info.get("is_pqc_cert", False)
            result["certificate_trusted"] = cert_info.get("certificate_trusted", False)

        result["overall_readiness"] = "ready" if evidence["transport_pqc"] else "not_ready"
        result["passed"] = evidence["verification_status"] == "verified" and bool(evidence["transport_pqc"])
        result["grade"] = "A+" if result["passed"] else "B" if evidence["verification_status"] == "verified" else "E"
        result["status_badge"] = "pqc-ready" if result["passed"] else "classical-13" if evidence["verification_status"] == "verified" else "error"
        result["status_title"] = (
            "ผ่าน (PQC Transport Verified)" if result["passed"]
            else "ยังไม่ผ่าน (Classical / Non-PQC)" if evidence["verification_status"] == "verified"
            else "ไม่สามารถยืนยันผลได้"
        )
        result["status_title_en"] = (
            "PASSED (PQC Transport Verified)" if result["passed"]
            else "NOT PASSED (Classical / Non-PQC)" if evidence["verification_status"] == "verified"
            else "Verification Failed"
        )
        result["reason_en"] = (
            "Verified TLS 1.3 PQC transport." if result["passed"]
            else "Verified TLS 1.3 without a standardized PQC transport group."
            if evidence["verification_status"] == "verified"
            else evidence.get("error") or "TLS evidence is incomplete."
        )
        result["reason_th"] = (
            "ยืนยัน TLS 1.3 PQC transport แล้ว" if result["passed"]
            else "ยืนยัน TLS 1.3 แล้ว แต่ไม่พบ standardized PQC transport group"
            if evidence["verification_status"] == "verified"
            else evidence.get("error") or "หลักฐาน TLS ไม่ครบถ้วน"
        )
    except Exception as exc:
        result["verification_status"] = "error"
        result["overall_readiness"] = "unknown"
        result["error"] = str(exc)
        result["status_title"] = "เกิดข้อผิดพลาดในการสแกน"
        result["status_title_en"] = "Scan Error"
        result["reason_th"] = f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {exc}"
        result["reason_en"] = f"Connection / Scan failed: {exc}"

    result["latency_ms"] = round((time.time() - start_time) * 1000, 1)
    return result
