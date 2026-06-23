"""FastAPI application entry point.

Wires the lifespan (workspace dir + DB init), CORS, and the route modules.
Run with: uvicorn main:app --reload
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health, runs
from config import get_settings
from database import init_db

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.workspace_dir, exist_ok=True)
    await init_db()
    yield


app = FastAPI(title="Mend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev: allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(runs.router)
