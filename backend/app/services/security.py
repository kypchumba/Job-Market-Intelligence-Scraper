import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque

from fastapi import Header, HTTPException, Request, status

from ..config import settings


def verify_scrape_access(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    valid_keys = {key for key in settings.scrape_api_keys if key}
    if not valid_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scrape API keys are not configured.",
        )

    token = _extract_token(authorization=authorization, x_api_key=x_api_key)
    if token not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API credentials are required for scrape access.",
        )


def _extract_token(authorization: str | None, x_api_key: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


@dataclass
class ScrapeGuard:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    request_log: dict[str, Deque[float]] = field(default_factory=lambda: defaultdict(deque))
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None

    async def enter(self, client_id: str) -> None:
        self._enforce_rate_limit(client_id)
        self._enforce_cooldown()
        if self.lock.locked():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A scrape is already running. Try again shortly.",
            )
        await self.lock.acquire()
        self.last_started_at = datetime.now(timezone.utc)

    def exit(self) -> None:
        self.last_finished_at = datetime.now(timezone.utc)
        if self.lock.locked():
            self.lock.release()

    def _enforce_rate_limit(self, client_id: str) -> None:
        now = time.monotonic()
        window = settings.scrape_rate_limit_window_seconds
        limit = settings.scrape_rate_limit_requests
        history = self.request_log[client_id]

        while history and now - history[0] > window:
            history.popleft()

        if len(history) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {limit} scrape requests per {window} seconds.",
            )

        history.append(now)

    def _enforce_cooldown(self) -> None:
        if not self.last_finished_at:
            return

        elapsed = (datetime.now(timezone.utc) - self.last_finished_at).total_seconds()
        remaining = settings.scrape_cooldown_seconds - elapsed
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Scrape cooldown active. Try again in {int(remaining) + 1} seconds.",
            )


def get_client_id(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
