"""WebSocket routes for real-time updates."""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from realtime import get_manager, get_ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time updates.

    Query Parameters:
    - client_id: Unique client identifier
    - token: Authentication token (optional)

    Messages:
    Client -> Server:
    {
        "action": "subscribe|unsubscribe",
        "channel": "signals|positions|agents|market|system"
    }

    Server -> Client:
    {
        "type": "message|history",
        "channel": "...",
        "data": {...}
    }
    """
    manager = get_ws_manager()

    # Generate client_id if not provided
    if not client_id:
        import uuid
        client_id = str(uuid.uuid4())[:8]

    await manager.connect(websocket, client_id)

    # Send welcome message with client ID
    await manager.send_to_client(client_id, {
        "type": "connected",
        "client_id": client_id,
        "message": "Connected to AI Agent Platform real-time service"
    })

    try:
        while True:
            # Receive and process client messages
            data = await websocket.receive_json()

            action = data.get("action")
            channel = data.get("channel")

            if action == "subscribe" and channel:
                success = await manager.subscribe(client_id, channel)
                await manager.send_to_client(client_id, {
                    "type": "subscription",
                    "channel": channel,
                    "status": "subscribed" if success else "failed"
                })

            elif action == "unsubscribe" and channel:
                success = await manager.unsubscribe(client_id, channel)
                await manager.send_to_client(client_id, {
                    "type": "subscription",
                    "channel": channel,
                    "status": "unsubscribed" if success else "failed"
                })

            elif action == "ping":
                await manager.send_to_client(client_id, {
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })

            elif action == "get_stats":
                stats = manager.get_stats()
                await manager.send_to_client(client_id, {
                    "type": "stats",
                    "data": stats
                })

            else:
                await manager.send_to_client(client_id, {
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_ws_manager()
    return manager.get_stats()