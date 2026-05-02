from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.constants import HANDLER_TIMEOUT, MONITOR_VERSION, PROJECTS, SUPPORTED_API_MAJOR  # noqa: F401
from server.db import apply_pending_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_pending_migrations()
    yield


app = FastAPI(title="Loop Monitor", lifespan=lifespan)

from server.routes import (  # noqa: E402
    action_queue,
    board,
    claude_usage,
    feed,
    graph,
    health,
    ingest,
    runs,
    stats,
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(board.router)
app.include_router(feed.router)
app.include_router(runs.router)
app.include_router(stats.router)
app.include_router(graph.router)
app.include_router(action_queue.router)
app.include_router(claude_usage.router)

app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=18792)
