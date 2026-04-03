"""FastAPI application for AI Agent Platform."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import all route modules
try:
    from telegram_routes import router as telegram_router
    from websocket_routes import router as websocket_router
    from provider_routes import router as provider_router
    from realtime import get_manager
except ImportError as e:
    print(f"Warning: Could not import some routes: {e}")
    telegram_router = None
    websocket_router = None
    provider_router = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("🚀 Starting AI Agent Platform API...")
    print(f"   Provider: {os.getenv('MODEL_PROVIDER', 'fireworks')}")
    print(f"   Model: {os.getenv('MODEL_NAME', 'accounts/fireworks/routers/kimi-k2p5-turbo')}")

    # Initialize connections
    yield

    print("🛑 Shutting down AI Agent Platform API...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="AI Agent Platform API",
        description="Autonomous cryptocurrency trading and analysis platform",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "https://ai-agent-dashboard.vercel.app",
            "*",  # Allow all for development
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    if telegram_router:
        app.include_router(telegram_router)
    if websocket_router:
        app.include_router(websocket_router)
    if provider_router:
        app.include_router(provider_router)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "api": "running",
                "database": "unknown",  # Will be updated when DB is connected
                "redis": "unknown"
            }
        }

    # WebSocket for real-time updates
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_json({
                    "type": "echo",
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
        except WebSocketDisconnect:
            print("WebSocket disconnected")

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "name": "AI Agent Platform API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "endpoints": {
                "agents": "/api/v1/agents",
                "strategies": "/api/v1/strategies",
                "signals": "/api/v1/signals",
                "providers": "/api/v1/providers",
                "telegram": "/api/v1/telegram",
                "health": "/health",
                "websocket": "/ws"
            }
        }

    return app


# Import datetime here to avoid circular import
from datetime import datetime

# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "true").lower() == "true",
        workers=int(os.getenv("API_WORKERS", "1")) if not os.getenv("API_RELOAD") else 1
    )
