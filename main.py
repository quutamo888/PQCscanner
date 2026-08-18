import os
import asyncio
import json
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pqc_probe import scan_pqc
from subdomain_finder import discover_subdomains
from cbom_exporter import generate_cbom

app = FastAPI(
    title="PQC Compliance Web Scanner",
    description="Post-Quantum Cryptography (PQC) Readiness Scanner for Websites",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SingleScanRequest(BaseModel):
    url: str
    timeout: Optional[float] = 4.0

class BatchScanRequest(BaseModel):
    urls: List[str]
    timeout: Optional[float] = 4.0
    concurrency: Optional[int] = 5

class DiscoverSubdomainsRequest(BaseModel):
    domain: str
    check_dns: Optional[bool] = True
    max_results: Optional[int] = 100

class CbomExportRequest(BaseModel):
    results: List[dict]

PRESETS = [
    {
        "category": "PQC Enabled Sites (ควอนตัมเรดี้ / Hybrid KEM)",
        "urls": [
            "https://pq.cloudflareresearch.com",
            "https://cloudflare.com",
            "https://google.com",
            "https://facebook.com",
            "https://instagram.com"
        ]
    },
    {
        "category": "Classical TLS 1.3 Sites (ยังเป็นคริปโตแบบดั้งเดิม)",
        "urls": [
            "https://github.com",
            "https://wikipedia.org",
            "https://apple.com",
            "https://amazon.com",
            "https://microsoft.com"
        ]
    },
    {
        "category": "Thai Government & Services (ทดสอบเว็บหน่วยงานไทย)",
        "urls": [
            "https://www.thaigov.go.th",
            "https://www.dga.or.th",
            "https://www.etda.or.th",
            "https://www.bot.or.th"
        ]
    }
]

@app.get("/api/presets")
async def get_presets():
    return PRESETS

@app.post("/api/discover-subdomains")
async def discover_subdomains_api(req: DiscoverSubdomainsRequest):
    return await discover_subdomains(
        domain=req.domain,
        check_dns=req.check_dns if req.check_dns is not None else True,
        max_results=req.max_results or 100
    )

@app.post("/api/export-cbom")
async def export_cbom_endpoint(req: CbomExportRequest):
    return generate_cbom(req.results)

@app.post("/api/scan")
async def scan_single_endpoint(req: SingleScanRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, scan_pqc, req.url, req.timeout or 4.0)
    return result

@app.post("/api/scan-stream")
async def scan_batch_stream(req: BatchScanRequest):
    raw_urls = [u.strip() for u in req.urls if u.strip()]
    unique_urls = list(dict.fromkeys(raw_urls))
    timeout = max(1.0, min(req.timeout or 4.0, 15.0))
    concurrency = max(1, min(req.concurrency or 3, 10))

    async def ndjson_generator():
        total = len(unique_urls)
        yield json.dumps({"event": "scan_start", "total": total}) + "\n"

        sem = asyncio.Semaphore(concurrency)
        queue: asyncio.Queue = asyncio.Queue()

        async def worker(url_target: str, idx: int):
            async with sem:
                await asyncio.sleep(idx * 0.05) # Stagger requests to prevent session / rate limit blocking
                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(None, scan_pqc, url_target, timeout)
                res["index"] = idx
                await queue.put(res)

        # Launch all tasks FIRST, then drain the queue
        tasks = [asyncio.create_task(worker(u, i)) for i, u in enumerate(unique_urls)]

        completed = 0
        passed_count = 0
        failed_count = 0

        while completed < total:
            res = await queue.get()
            completed += 1
            if res.get("passed"):
                passed_count += 1
            else:
                failed_count += 1

            payload = {
                "event": "scan_result",
                "completed": completed,
                "total": total,
                "percent": round((completed / total) * 100),
                "result": res
            }
            yield json.dumps(payload) + "\n"
            queue.task_done()

        await asyncio.gather(*tasks)

        yield json.dumps({
            "event": "scan_complete",
            "total": total,
            "passed": passed_count,
            "failed": failed_count
        }) + "\n"

    return StreamingResponse(
        ndjson_generator(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}
    )

# Mount static folder
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=FileResponse)
@app.get("/index.html", response_class=FileResponse)
@app.get("/api", response_class=FileResponse)
@app.get("/api/index", response_class=FileResponse)
async def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
