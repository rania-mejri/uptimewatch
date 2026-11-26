import logging
import os
import time

import httpx
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import Check, Monitor

INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
TIMEOUT = float(os.getenv("CHECK_TIMEOUT_SECONDS", "10"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("checker")

CHECKS = Counter(
    "uptimewatch_checks_total",
    "Verifications effectuees",
    ["monitor", "result"],
)
UP = Gauge(
    "uptimewatch_monitor_up",
    "1 si le site repond, 0 sinon",
    ["monitor"],
)
RESPONSE = Histogram(
    "uptimewatch_response_seconds",
    "Temps de reponse",
    ["monitor"],
)


def check_one(client: httpx.Client, monitor: Monitor):
    start = time.perf_counter()
    try:
        r = client.get(monitor.url)
    except httpx.HTTPError as exc:
        log.warning("echec %s : %s", monitor.url, exc)
        return Check(monitor_id=monitor.id, is_up=False), None
    elapsed = time.perf_counter() - start
    is_up = r.status_code < 400
    check = Check(
        monitor_id=monitor.id,
        is_up=is_up,
        status_code=r.status_code,
        response_ms=round(elapsed * 1000, 1),
    )
    return check, elapsed


def run_once():
    with (
        SessionLocal() as db,
        httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client,
    ):
        for monitor in db.scalars(select(Monitor)).all():
            check, elapsed = check_one(client, monitor)
            db.add(check)
            UP.labels(monitor.name).set(1 if check.is_up else 0)
            result = "up" if check.is_up else "down"
            CHECKS.labels(monitor.name, result).inc()
            if elapsed is not None:
                RESPONSE.labels(monitor.name).observe(elapsed)
            log.info("%s -> %s", monitor.name, result.upper())
        db.commit()


def main():
    Base.metadata.create_all(bind=engine)
    start_http_server(int(os.getenv("METRICS_PORT", "9101")))
    log.info("checker demarre, intervalle %ss", INTERVAL)
    while True:
        try:
            run_once()
        except Exception:
            log.exception("erreur pendant le cycle")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
