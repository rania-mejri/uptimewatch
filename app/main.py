import html
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from .models import Check, Monitor

API_KEY = os.getenv("API_KEY", "")

REQUESTS = Counter(
    "http_requests_total",
    "Requetes HTTP recues",
    ["method", "status"],
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duree des requetes HTTP",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="UptimeWatch", lifespan=lifespan)


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    LATENCY.observe(time.perf_counter() - start)
    REQUESTS.labels(request.method, str(response.status_code)).inc()
    return response


def require_api_key(x_api_key: str = Header(default="")):
    if not API_KEY or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Cle API invalide")


class MonitorIn(BaseModel):
    name: str
    url: HttpUrl


class MonitorOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    url: str


class CheckOut(BaseModel):
    model_config = {"from_attributes": True}
    checked_at: datetime
    is_up: bool
    status_code: int | None
    response_ms: float | None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post(
    "/monitors",
    response_model=MonitorOut,
    status_code=201,
    dependencies=[Depends(require_api_key)],
)
def create_monitor(data: MonitorIn, db: Session = Depends(get_db)):
    monitor = Monitor(name=data.name, url=str(data.url))
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@app.get("/monitors", response_model=list[MonitorOut])
def list_monitors(db: Session = Depends(get_db)):
    return db.scalars(select(Monitor).order_by(Monitor.id)).all()


@app.delete(
    "/monitors/{monitor_id}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)):
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Moniteur introuvable")
    db.delete(monitor)
    db.commit()


@app.get("/monitors/{monitor_id}/checks", response_model=list[CheckOut])
def list_checks(
    monitor_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Moniteur introuvable")
    query = (
        select(Check)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc())
        .limit(limit)
    )
    return db.scalars(query).all()


@app.get("/", response_class=HTMLResponse)
def status_page(db: Session = Depends(get_db)):
    rows = ""
    for m in db.scalars(select(Monitor).order_by(Monitor.id)).all():
        last_query = (
            select(Check)
            .where(Check.monitor_id == m.id)
            .order_by(Check.checked_at.desc())
            .limit(1)
        )
        last = db.scalars(last_query).first()
        if last is None:
            state = "en attente"
        elif last.is_up:
            state = "UP"
        else:
            state = "DOWN"
        name = html.escape(m.name)
        url = html.escape(m.url)
        rows += f"<tr><td>{name}</td><td>{url}</td><td>{state}</td></tr>"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>UptimeWatch</title></head>"
        "<body><h1>UptimeWatch</h1>"
        "<table border='1' cellpadding='6'>"
        "<tr><th>Nom</th><th>URL</th><th>Etat</th></tr>"
        f"{rows}</table></body></html>"
    )
