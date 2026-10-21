"""Cliente HTTP "educado": respeta robots.txt, espera entre peticiones y guarda evidencia de cada descarga."""
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from automarket_pipeline.config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS, USER_AGENT

MAX_ATTEMPTS = 3


class PoliteClient:
    def __init__(self, raw_dir: Path, log: logging.Logger):
        self.raw_dir = raw_dir
        self.log = log
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "es-MX,es;q=0.9"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request = 0.0
        self.manifest: list[dict] = []

    # ---------- robots.txt ----------
    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            self._wait()
            resp = self.http.get(f"{origin}/robots.txt")
            if resp.status_code in (401, 403):
                rp.disallow_all = True  # el sitio no permite bots
            elif resp.status_code >= 400:
                rp.allow_all = True  # sin robots.txt: se permite (estándar RFC 9309)
            else:
                rp.parse(resp.text.splitlines())
            self.log.info("robots.txt %s -> HTTP %s", origin, resp.status_code)
            self._robots[origin] = rp
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(USER_AGENT, url)

    # ---------- descargas ----------
    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request = time.monotonic()

    def get(self, url: str, save_as: str) -> str | None:
        """Descarga una URL permitida, guarda el contenido en raw/<run_id>/<save_as> y lo devuelve."""
        entry = {"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(), "file": save_as}
        if not self.allowed(url):
            self.log.warning("Bloqueado por robots.txt, se omite: %s", url)
            self.manifest.append({**entry, "status": "bloqueado_robots"})
            return None

        resp = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait()
            try:
                resp = self.http.get(url)
                break
            except httpx.HTTPError as exc:
                self.log.warning("Intento %d/%d falló en %s: %s", attempt, MAX_ATTEMPTS, url, exc)
                if attempt == MAX_ATTEMPTS:
                    self.manifest.append({**entry, "status": "error_red", "detail": str(exc)})
                    return None
                time.sleep(REQUEST_DELAY_SECONDS * 2 ** attempt)  # espera creciente: 4 s, 8 s
        entry["attempts"] = attempt

        body = resp.content
        path = self.raw_dir / save_as
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.manifest.append({
            **entry,
            "status": "ok" if resp.status_code == 200 else "http_error",
            "http_status": resp.status_code,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
        self.log.info("GET %s -> %s (%s KB)", url, resp.status_code, len(body) // 1024)
        return resp.text if resp.status_code == 200 else None

    def write_manifest(self, path: Path) -> None:
        path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def close(self) -> None:
        self.http.close()
