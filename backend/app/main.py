from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.timeutil import to_iso_z
from app.services.seed import seed_database

# FastAPI jsonable_encoder bypasses Pydantic serializers for datetime; force Zulu ISO.
ENCODERS_BY_TYPE[datetime] = lambda value: to_iso_z(value) or ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.models import Payment

        count = db.query(Payment).count()
        if count == 0:
            seed_database(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Finance Control Tower API",
        description="AI-powered financial control and exception management",
        version="1.0.0",
        lifespan=lifespan,
    )

    origins = settings.cors_origin_list
    allow_credentials = True
    if origins == ["*"] or settings.cors_origins.strip() == "*":
        origins = ["*"]
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    # Production / Render: serve built React app from ./static
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if settings.serve_frontend and static_dir.is_dir():
        assets = static_dir / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        async def spa_root():
            return FileResponse(static_dir / "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # Do not swallow API / docs routes
            if full_path.startswith(("api/", "docs", "redoc", "openapi")):
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not found")
            candidate = static_dir / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
