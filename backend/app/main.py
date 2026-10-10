import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings
from app.container import build_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    c = build_container(get_settings())
    if c.store.count() == 0:
        c.ingest()
    app.state.container = c
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Acme Second Brain", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    if s.frontend_dist.is_dir():  # single-container deploy: serve the built React app
        app.mount("/", StaticFiles(directory=s.frontend_dist, html=True), name="frontend")
    return app


app = create_app()
