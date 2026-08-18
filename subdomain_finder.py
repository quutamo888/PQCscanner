import asyncio
import socket
import urllib.request
import urllib.parse
import json
import re
from typing import List, Set, Dict, Any

COMMON_SUBDOMAINS = [
    "www", "api", "mail", "dev", "app", "auth", "m", "admin", "portal", "vpn", 
    "cdn", "test", "beta", "cloud", "login", "gateway", "secure", "web", "staging", 
    "shop", "pay", "id", "sso", "ns1", "ns2", "smtp", "remote", "status", 
    "docs", "help", "support", "static", "media", "dashboard", "connect", "git", 
    "internal", "corp", "autodiscover", "webmail", "account", "accounts", "identity",
    "oauth", "chat", "meeting", "meet", "blog", "news", "direct", "ipv6", "stage",
    "sandbox", "qa", "uat", "demo", "billing", "my", "member", "service", "services",
    "hub", "console", "space", "lab", "labs", "static1", "static2", "assets", "img",
    "data", "analytics", "track", "metrics", "monitor", "grafana", "kibana", "elastic"
]

def clean_domain(raw_input: str) -> str:
    raw = raw_input.strip().lower()
    raw = re.sub(r'^https?://', '', raw)
    raw = raw.split('/')[0].split(':')[0]
    return raw

def fetch_crt_sh(domain: str, timeout: float = 4.0) -> Set[str]:
    found = set()
    url = f"https://crt.sh/?q=%.{urllib.parse.quote(domain)}&output=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PQC-Scanner/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                for entry in data:
                    name_value = entry.get('name_value', '')
                    for sub in name_value.split('\n'):
                        sub = sub.strip().lower()
                        if '*' in sub:
                            sub = sub.replace('*.', '')
                        if (sub.endswith(f".{domain}") or sub == domain) and not re.search(r'[^a-z0-9.-]', sub):
                            if len(sub) > 0:
                                found.add(sub)
    except Exception:
        pass
    return found

def fetch_hackertarget(domain: str, timeout: float = 4.0) -> Set[str]:
    found = set()
    url = f"https://api.hackertarget.com/hostsearch/?q={urllib.parse.quote(domain)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PQC-Scanner/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                content = resp.read().decode('utf-8', errors='ignore')
                for line in content.splitlines():
                    parts = line.split(',')
                    if parts:
                        sub = parts[0].strip().lower()
                        if (sub.endswith(f".{domain}") or sub == domain) and not re.search(r'[^a-z0-9.-]', sub):
                            found.add(sub)
    except Exception:
        pass
    return found

def resolve_dns_sync(hostname: str, timeout: float = 2.0) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False

async def discover_subdomains(domain: str, check_dns: bool = True, max_results: int = 150) -> Dict[str, Any]:
    dom = clean_domain(domain)
    if not dom or '.' not in dom:
        return {"domain": domain, "total_found": 0, "subdomains": [], "error": "Invalid domain format"}

    candidates: Set[str] = set()
    candidates.add(dom)
    candidates.add(f"www.{dom}")

    # Add dictionary wordlist
    for word in COMMON_SUBDOMAINS:
        candidates.add(f"{word}.{dom}")

    # Query passive discovery APIs in parallel
    loop = asyncio.get_event_loop()
    crt_task = loop.run_in_executor(None, fetch_crt_sh, dom, 4.0)
    ht_task = loop.run_in_executor(None, fetch_hackertarget, dom, 4.0)
    
    results = await asyncio.gather(crt_task, ht_task, return_exceptions=True)
    for res in results:
        if isinstance(res, set):
            candidates.update(res)

    # Concurrently verify DNS reachability
    active_subdomains: List[str] = []
    if check_dns:
        sem = asyncio.Semaphore(15)

        async def check_host(host: str):
            async with sem:
                ok = await loop.run_in_executor(None, resolve_dns_sync, host, 2.0)
                if ok:
                    active_subdomains.append(host)

        tasks = [check_host(h) for h in candidates]
        await asyncio.gather(*tasks)
    else:
        active_subdomains = list(candidates)

    def sort_key(s: str):
        if s == dom:
            return (0, s)
        if s == f"www.{dom}":
            return (1, s)
        return (2, s)

    sorted_subs = sorted(list(set(active_subdomains)), key=sort_key)
    if max_results and len(sorted_subs) > max_results:
        sorted_subs = sorted_subs[:max_results]

    urls = [f"https://{s}" for s in sorted_subs]
    return {
        "domain": dom,
        "total_found": len(sorted_subs),
        "subdomains": urls,
        "raw_hosts": sorted_subs
    }
