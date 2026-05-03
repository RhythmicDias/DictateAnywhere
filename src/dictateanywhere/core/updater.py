"""
Auto-update checker.

Silently checks the GitHub releases API at startup (after a 15-second
delay) and calls the on_update_available callback when a newer version
is found.  Checks at most once per 24 hours; users can skip a specific
version so they are not reminded again for that release.

Usage
─────
    checker = UpdateChecker(config_manager, current_version="1.0.0")
    checker.start(on_update_available=my_callback)

The callback signature:
    on_update_available(latest: str, url: str) -> None

Thread-safety
─────────────
The network request runs on a daemon thread.  The callback is invoked
on that same thread — callers must marshal to the GUI thread if needed
(use root.after(0, ...) in main.py).
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from datetime import date
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_API_URL    = "https://api.github.com/repos/stephendias-NPD/DictateAnywhere/releases/latest"
_RELEASES   = "https://github.com/stephendias-NPD/DictateAnywhere/releases/latest"
_UA         = "DictateAnywhere-UpdateChecker/1.0"
_TIMEOUT    = 10          # seconds for the HTTP request
_STARTUP_DELAY = 15       # seconds after launch before checking


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse 'v1.2.3' or '1.2.3' into (1, 2, 3)."""
    v = v.strip().lstrip("v").lstrip("V")
    try:
        return tuple(int(x) for x in v.split(".") if x.isdigit())
    except Exception:
        return (0,)


class UpdateChecker:
    """Background update checker against the GitHub releases API."""

    def __init__(self, config_manager, current_version: str) -> None:
        self._cfg     = config_manager
        self._current = current_version
        self._thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self, on_update_available: Callable[[str, str], None]) -> None:
        """
        Schedule a background update check.

        Respects:
        - config 'check_updates' = False  → skip entirely
        - config 'last_update_check' == today → already checked today, skip
        - config 'skipped_update_version' == latest → user dismissed this release
        """
        if not self._cfg.get("check_updates", True):
            logger.debug("Update check disabled in settings")
            return

        self._thread = threading.Thread(
            target=self._worker,
            args=(on_update_available,),
            name="update-checker",
            daemon=True,
        )
        self._thread.start()

    def check_now(self, on_result: Callable[[str, str, bool], None]) -> None:
        """
        Immediate check (called from Settings 'Check now' button).

        Calls on_result(latest_version, release_url, is_newer) regardless
        of the 24-hour cache or skip-version setting.
        """
        threading.Thread(
            target=self._immediate_worker,
            args=(on_result,),
            name="update-checker-manual",
            daemon=True,
        ).start()

    # ── Workers ────────────────────────────────────────────────────────────────

    def _worker(self, callback: Callable[[str, str], None]) -> None:
        """Delayed background check with all throttle/skip guards."""
        # Respect 24-hour cooldown
        last = self._cfg.get("last_update_check", "")
        today = date.today().isoformat()
        if last == today:
            logger.debug("Update already checked today (%s) — skipping", today)
            return

        # Wait before hitting the network so startup feels instant
        threading.Event().wait(_STARTUP_DELAY)

        latest, url = self._fetch_latest()
        if not latest:
            return

        # Record that we checked today
        try:
            self._cfg.set("last_update_check", today)
            self._cfg.save()
        except Exception:
            pass

        # Skip if the user already dismissed this version
        skipped = self._cfg.get("skipped_update_version", "")
        if skipped and _parse_version(skipped) >= _parse_version(latest):
            logger.debug("Version %s is skipped by user preference", latest)
            return

        if _parse_version(latest) > _parse_version(self._current):
            logger.info("Update available: %s → %s", self._current, latest)
            callback(latest, url)
        else:
            logger.info("Already up to date (%s)", self._current)

    def _immediate_worker(
        self, callback: Callable[[str, str, bool], None]
    ) -> None:
        """No delay, no throttle — used by the manual 'Check now' button."""
        latest, url = self._fetch_latest()
        if latest:
            is_newer = _parse_version(latest) > _parse_version(self._current)
            callback(latest, url, is_newer)
        else:
            callback("", _RELEASES, False)

    # ── Network ────────────────────────────────────────────────────────────────

    def _fetch_latest(self) -> tuple[str, str]:
        """Return (tag_name, html_url) or ('', '') on failure."""
        try:
            req = urllib.request.Request(
                _API_URL,
                headers={"User-Agent": _UA,
                         "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "").strip()
            url = data.get("html_url", _RELEASES).strip()
            logger.debug("Latest GitHub release: %s", tag)
            return tag, url
        except urllib.error.URLError as exc:
            logger.debug("Update check failed (network): %s", exc)
        except Exception as exc:
            logger.debug("Update check failed: %s", exc)
        return "", ""

    # ── Skip version ───────────────────────────────────────────────────────────

    def skip_version(self, version: str) -> None:
        """Persist a skip preference so this release is never shown again."""
        try:
            self._cfg.set("skipped_update_version", version)
            self._cfg.save()
            logger.info("Skipping update version: %s", version)
        except Exception as exc:
            logger.warning("Could not save skip preference: %s", exc)
