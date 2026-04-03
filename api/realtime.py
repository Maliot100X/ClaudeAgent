"""Real-time WebSocket manager for live updates."""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manage WebSocket connections for real-time updates.

    Features:
    - Connection pooling
    - Room/channel-based subscriptions
    - Broadcast and targeted messaging
    - Automatic reconnection handling
    """

    def __init__(self):
        # Active connections
        self.active_connections: Dict[str, WebSocket] = {}

        # Rooms (channels) with their connected clients
        self.rooms: Dict[str, Set[str]] = {
            "signals": set(),
            "positions": set(),
            "agents": set(),
            "market": set(),
            "system": set(),
        }

        # Message history for replay on reconnection
        self.message_history: Dict[str, list] = {
            "signals": [],
            "positions": [],
            "agents": [],
        }
        self.max_history = 100

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected. Total: {len(self.active_connections)}")

    def disconnect(self, client_id: str) -> None:
        """Remove a connection and clean up subscriptions."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

        # Remove from all rooms
        for room in self.rooms.values():
            room.discard(client_id)

        logger.info(f"Client {client_id} disconnected. Total: {len(self.active_connections)}")

    async def subscribe(self, client_id: str, room: str) -> bool:
        """Subscribe a client to a room."""
        if room not in self.rooms:
            return False

        if client_id not in self.active_connections:
            return False

        self.rooms[room].add(client_id)
        logger.info(f"Client {client_id} subscribed to {room}")

        # Send message history for context
        if room in self.message_history and self.message_history[room]:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_json({
                    "type": "history",
                    "channel": room,
                    "data": self.message_history[room][-20:]  # Last 20 messages
                })
            except Exception as e:
                logger.error(f"Failed to send history to {client_id}: {e}")

        return True

    async def unsubscribe(self, client_id: str, room: str) -> bool:
        """Unsubscribe a client from a room."""
        if room in self.rooms:
            self.rooms[room].discard(client_id)
            logger.info(f"Client {client_id} unsubscribed from {room}")
            return True
        return False

    async def broadcast(self, room: str, message: dict) -> None:
        """Broadcast a message to all subscribers of a room."""
        if room not in self.rooms:
            return

        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()

        # Store in history
        if room in self.message_history:
            self.message_history[room].append(message)
            if len(self.message_history[room]) > self.max_history:
                self.message_history[room] = self.message_history[room][-self.max_history:]

        # Send to all subscribers
        disconnected = []
        for client_id in list(self.rooms[room]):
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json({
                        "type": "message",
                        "channel": room,
                        "data": message
                    })
                except Exception as e:
                    logger.error(f"Failed to send to {client_id}: {e}")
                    disconnected.append(client_id)
            else:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_to_client(self, client_id: str, message: dict) -> bool:
        """Send a message to a specific client."""
        if client_id not in self.active_connections:
            return False

        try:
            await self.active_connections[client_id].send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send to {client_id}: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast_to_all(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        disconnected = []

        for client_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {client_id}: {e}")
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    def get_stats(self) -> dict:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "rooms": {
                room: len(clients) for room, clients in self.rooms.items()
            },
            "history_sizes": {
                room: len(msgs) for room, msgs in self.message_history.items()
            }
        }


class RealTimeManager:
    """
    High-level manager for real-time system integration.

    Coordinates between WebSocket connections and Redis Pub/Sub
    for cross-server message distribution.
    """

    def __init__(self, redis_client=None):
        self.ws_manager = ConnectionManager()
        self.redis = redis_client
        self._running = False
        self._pubsub_task: Optional[asyncio.Task] = None

        # Callbacks for different message types
        self._callbacks: Dict[str, list] = {
            "signal": [],
            "position": [],
            "agent_status": [],
            "market_update": [],
            "system_alert": [],
        }

    async def start(self) -> None:
        """Start the real-time manager."""
        self._running = True

        if self.redis:
            self._pubsub_task = asyncio.create_task(self._redis_listener())

        logger.info("Real-time manager started")

    async def stop(self) -> None:
        """Stop the real-time manager."""
        self._running = False

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for client_id in list(self.ws_manager.active_connections.keys()):
            self.ws_manager.disconnect(client_id)

        logger.info("Real-time manager stopped")

    async def _redis_listener(self) -> None:
        """Listen for Redis Pub/Sub messages."""
        if not self.redis:
            return

        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(*self._callbacks.keys())

            async for message in pubsub.listen():
                if not self._running:
                    break

                if message["type"] == "message":
                    channel = message["channel"].decode()
                    data = json.loads(message["data"])

                    # Forward to WebSocket clients
                    await self.ws_manager.broadcast(channel, data)

                    # Trigger callbacks
                    for callback in self._callbacks.get(channel, []):
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                asyncio.create_task(callback(data))
                            else:
                                callback(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def publish(self, channel: str, data: dict) -> None:
        """
        Publish a message to the real-time system.

        Broadcasts via WebSocket and publishes to Redis if available.
        """
        # Always broadcast to local WebSocket clients
        await self.ws_manager.broadcast(channel, data)

        # Also publish to Redis for other servers
        if self.redis:
            try:
                await self.redis.publish(channel, json.dumps(data))
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

    def register_callback(self, event_type: str, callback: Callable) -> None:
        """Register a callback for a specific event type."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    def unregister_callback(self, event_type: str, callback: Callable) -> None:
        """Unregister a callback."""
        if event_type in self._callbacks:
            self._callbacks[event_type] = [
                cb for cb in self._callbacks[event_type] if cb != callback
            ]

    # Convenience methods for common events

    async def publish_signal(self, signal: dict) -> None:
        """Publish a trading signal."""
        await self.publish("signals", {
            "type": "signal",
            "data": signal
        })

    async def publish_position_update(self, position: dict) -> None:
        """Publish a position update."""
        await self.publish("positions", {
            "type": "position_update",
            "data": position
        })

    async def publish_agent_status(self, agent_id: str, status: dict) -> None:
        """Publish agent status change."""
        await self.publish("agents", {
            "type": "agent_status",
            "agent_id": agent_id,
            "data": status
        })

    async def publish_market_update(self, symbol: str, data: dict) -> None:
        """Publish market data update."""
        await self.publish("market", {
            "type": "market_update",
            "symbol": symbol,
            "data": data
        })

    async def publish_system_alert(self, level: str, message: str, details: Optional[dict] = None) -> None:
        """Publish a system alert."""
        await self.publish("system", {
            "type": "alert",
            "level": level,
            "message": message,
            "details": details or {}
        })


# Global manager instance
_manager: Optional[RealTimeManager] = None


def get_manager(redis_client=None) -> RealTimeManager:
    """Get or create the global real-time manager."""
    global _manager
    if _manager is None:
        _manager = RealTimeManager(redis_client)
    return _manager


def get_ws_manager() -> ConnectionManager:
    """Get the WebSocket connection manager."""
    return get_manager().ws_manager