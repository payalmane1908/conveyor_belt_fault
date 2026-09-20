import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining clients: {len(self.active_connections)}")

    async def broadcast_json(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

    async def broadcast_burst(
        self,
        burst_id: str,
        device_id: str,
        stream_id: str,
        sensor_id: str,
        joint_id: Optional[str],
        sequence_number: int,
        hardware_timestamp_us: int,
        unwrapped_hardware_timestamp_us: int,
        received_at_utc: str,
        sampling_rate_hz: float,
        sample_count: int,
        sha256_hash: str,
        quality_flags: str,
        data_provenance: str,
        samples: List[float],
        stream_tracker: Optional[Dict[str, Any]] = None
    ):
        message = {
            "type": "TELEMETRY_BURST",
            "burst_id": burst_id,
            "device_id": device_id,
            "stream_id": stream_id,
            "sensor_id": sensor_id,
            "joint_id": joint_id,
            "sequence_number": sequence_number,
            "hardware_timestamp_us": hardware_timestamp_us,
            "unwrapped_hardware_timestamp_us": unwrapped_hardware_timestamp_us,
            "received_at_utc": received_at_utc,
            "sampling_rate_hz": sampling_rate_hz,
            "sample_count": sample_count,
            "sha256_hash": sha256_hash,
            "quality_flags": quality_flags,
            "data_provenance": data_provenance,
            "samples": samples,
            "stream_tracker": stream_tracker
        }
        await self.broadcast_json(message)

    def dispatch_burst(
        self,
        burst_id: str,
        device_id: str,
        stream_id: str,
        sensor_id: str,
        joint_id: Optional[str],
        sequence_number: int,
        hardware_timestamp_us: int,
        unwrapped_hardware_timestamp_us: int,
        received_at_utc: str,
        sampling_rate_hz: float,
        sample_count: int,
        sha256_hash: str,
        quality_flags: str,
        data_provenance: str,
        samples: List[float],
        stream_tracker: Optional[Dict[str, Any]] = None
    ):
        """Called by synchronous threads (e.g. serial worker) to dispatch asynchronously."""
        coro = self.broadcast_burst(
            burst_id=burst_id,
            device_id=device_id,
            stream_id=stream_id,
            sensor_id=sensor_id,
            joint_id=joint_id,
            sequence_number=sequence_number,
            hardware_timestamp_us=hardware_timestamp_us,
            unwrapped_hardware_timestamp_us=unwrapped_hardware_timestamp_us,
            received_at_utc=received_at_utc,
            sampling_rate_hz=sampling_rate_hz,
            sample_count=sample_count,
            sha256_hash=sha256_hash,
            quality_flags=quality_flags,
            data_provenance=data_provenance,
            samples=samples,
            stream_tracker=stream_tracker
        )
        self._schedule_coro(coro)

    def dispatch_json(self, message: Dict[str, Any]):
        """
        Thread-safe dispatch of any JSON message to all WebSocket clients.

        Used by HealthAssessmentService (synchronous context) to broadcast
        HEALTH_UPDATE and ALERT_TRIGGERED events without blocking.
        """
        coro = self.broadcast_json(message)
        self._schedule_coro(coro)

    def _schedule_coro(self, coro):
        """Schedule a coroutine on the running event loop, from any thread."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self._loop)
            else:
                coro.close()

ws_manager = WebSocketManager()
