"""PolicyDesk — FastAPI application entry point.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app.db import create_db_and_tables, engine
from app.routers import customers, pages, policies, products, quotes, claims
from app.seed import seed

BASE_DIR = Path(__file__).resolve().parent
APP_ENV = os.getenv("APP_ENV", "dev")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        seed(session)
    yield


app = FastAPI(
    title="PolicyDesk",
    description="A simplified insurance policy & claims API — TalentPath Academy AI-Powered SDLC Workshop.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(customers.router)
app.include_router(products.router)
app.include_router(quotes.router)
app.include_router(policies.router)
app.include_router(pages.router)
app.include_router(claims.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": "PolicyDesk", "env": APP_ENV}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/static/favicon.svg")
