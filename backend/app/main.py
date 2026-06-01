import logging
import logging.handlers
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth as auth_router
from app.routers import imports as imports_router
from app.routers import ue as ue_router

settings = get_settings()


def _configure_logging() -> None:
    import os
    log_dir = os.path.dirname(settings.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    yield


app = FastAPI(
    title="Chlorofile Web API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(imports_router.router)
app.include_router(ue_router.router)

# À ajouter au fur et à mesure :
# app.include_router(parcelles_router.router)
# app.include_router(validation_router.router)
# app.include_router(kizeo_router.router)
