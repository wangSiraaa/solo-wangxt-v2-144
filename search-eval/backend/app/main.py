from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .db import Base, engine
from .routers import experiments, judgments, meta

Base.metadata.create_all(engine)

app = FastAPI(title="Search Relevance Evaluation Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
api.include_router(meta.router)
api.include_router(judgments.router)
api.include_router(experiments.router)
app.include_router(api)

# Serve the built frontend (npm run build -> frontend/dist) if present.
dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist.is_dir():
    class SPAStaticFiles(StaticFiles):
        """StaticFiles with history-mode fallback to index.html."""

        async def get_response(self, path, scope):
            from starlette.exceptions import HTTPException as StarletteHTTP
            try:
                return await super().get_response(path, scope)
            except StarletteHTTP as exc:
                if exc.status_code == 404:
                    return await super().get_response("index.html", scope)
                raise

    app.mount("/", SPAStaticFiles(directory=dist, html=True), name="frontend")
