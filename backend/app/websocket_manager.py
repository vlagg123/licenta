from __future__ import annotations
import json
from typing import List
from fastapi import WebSocket
from datetime import datetime


def _serial(obj):
    if isinstance(obj, datetime):
        # sufixul Z marcheaza explicit UTC — fara el browser-ul interpreteaza ca ora locala
        return obj.isoformat() + "Z"
    raise TypeError(f"nu stiu sa serializez {type(obj)}")


class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active = [c for c in self.active if c is not ws]

    async def broadcast(self, data: dict) -> None:
        payload = json.dumps(data, default=_serial)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self.active)


manager = ConnectionManager()
