from __future__ import annotations

from fastapi import FastAPI

app = FastAPI()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def serve() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8099)
