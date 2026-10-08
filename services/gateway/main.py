"""API Gateway — Nginx-style routing for the modular monolith.

In production, use nginx/Caddy as reverse proxy.
This is a development HTTP gateway for internal service routing.
"""

from fastapi import FastAPI, Request, Response
import httpx

app = FastAPI(title="TopInjector Gateway", version="0.1.0")

# Internal service endpoints (same process in monolith mode)
SERVICES = {
    "/api/": "http://localhost:8000",  # Main API is the monolith itself
}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """Route requests to appropriate internal services."""
    for prefix, target in SERVICES.items():
        if request.url.path.startswith(prefix):
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=request.method,
                    url=f"{target}/api/{path}",
                    headers={k.decode(): v.decode() for k, v in request.headers.raw},
                    content=await request.body(),
                )
            return Response(
                content=resp.text,
                status_code=resp.status_code,
                headers=dict(resp.headers),
            )
    return Response("Not Found", status_code=404)
