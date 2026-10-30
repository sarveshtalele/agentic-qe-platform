from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Set


class StreamBroker:
    """Manages active Server-Sent Events subscriber queues for AG-UI."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._subscribers:
            self._subscribers[session_id] = set()
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        if session_id in self._subscribers:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def broadcast(self, session_id: str, event_type: str, data: Dict[str, Any]) -> None:
        if session_id not in self._subscribers:
            return
        payload = {
            "event": event_type,
            "data": data,
        }
        for q in list(self._subscribers[session_id]):
            try:
                await q.put(payload)
            except Exception:
                pass

    async def event_generator(self, session_id: str, queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        # Send initial connection handshake
        yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"
        try:
            while True:
                try:
                    # Wait for next event or heartbeat timeout (15s)
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    evt_type = payload.get("event", "message")
                    data_str = json.dumps(payload.get("data", {}))
                    yield f"event: {evt_type}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat ping
                    yield f"event: ping\ndata: {{}}\n\n"
        finally:
            self.unsubscribe(session_id, queue)


# Global stream broker instance
global_stream_broker = StreamBroker()
