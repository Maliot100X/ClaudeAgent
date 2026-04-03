"""Model/Provider management routes."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import asyncio

from providers.base import ProviderType
from providers.factory import ProviderFactory

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    id: str
    name: str
    status: str
    models: List[str]
    current: bool = False


class CurrentProvider(BaseModel):
    provider: str
    model: str
    config: Dict[str, Any]


class SetProviderRequest(BaseModel):
    provider: str
    model: Optional[str] = None


class ProviderTestResponse(BaseModel):
    success: bool
    latency_ms: float
    test_output: str


# Available models per provider
AVAILABLE_MODELS = {
    "fireworks": {
        "name": "Fireworks AI",
        "models": [
            "accounts/fireworks/routers/kimi-k2p5-turbo",
            "accounts/fireworks/models/llama-v3p1-70b-instruct",
            "accounts/fireworks/models/mixtral-8x22b-instruct",
        ]
    },
    "ollama": {
        "name": "Ollama",
        "models": [
            "minimax-m2:cloud",
            "deepseek-v3.2:cloud",
            "glm-4.6:cloud",
            "llama3.2:latest",
            "qwen2.5:latest",
        ]
    },
    "gemini": {
        "name": "Google Gemini",
        "models": [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-pro",
        ]
    },
    "openai": {
        "name": "OpenAI",
        "models": [
            "gpt-4-turbo-preview",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
    }
}


def get_current_provider_info() -> Dict[str, Any]:
    """Get current provider configuration."""
    provider = os.getenv("MODEL_PROVIDER", "fireworks")
    model = os.getenv("MODEL_NAME", "accounts/fireworks/routers/kimi-k2p5-turbo")

    return {
        "provider": provider,
        "model": model,
        "config": {
            "temperature": float(os.getenv("MODEL_TEMPERATURE", "0.7")),
            "max_tokens": int(os.getenv("MODEL_MAX_TOKENS", "4096")),
            "timeout": int(os.getenv("MODEL_TIMEOUT", "60"))
        }
    }


@router.get("/", response_model=List[ProviderInfo])
async def list_providers():
    """List all available AI providers and their models."""
    current = get_current_provider_info()
    providers = []

    for provider_id, info in AVAILABLE_MODELS.items():
        # Check if provider is configured
        status = "inactive"
        if provider_id == "fireworks" and os.getenv("FIREWORKS_API_KEY"):
            status = "active"
        elif provider_id == "ollama" and os.getenv("OLLAMA_API_KEY"):
            status = "active"
        elif provider_id == "gemini" and os.getenv("GOOGLE_API_KEY"):
            status = "active"
        elif provider_id == "openai" and os.getenv("OPENAI_API_KEY"):
            status = "active"

        providers.append(ProviderInfo(
            id=provider_id,
            name=info["name"],
            status=status,
            models=info["models"],
            current=(provider_id == current["provider"])
        ))

    return providers


@router.get("/current", response_model=CurrentProvider)
async def get_current_provider():
    """Get currently active provider."""
    return CurrentProvider(**get_current_provider_info())


@router.post("/set")
async def set_provider(request: SetProviderRequest):
    """Switch AI provider and model."""
    provider_id = request.provider.lower()

    if provider_id not in AVAILABLE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider: {provider_id}. Available: {list(AVAILABLE_MODELS.keys())}"
        )

    # Check if provider is configured
    if provider_id == "fireworks" and not os.getenv("FIREWORKS_API_KEY"):
        raise HTTPException(status_code=400, detail="Fireworks API key not configured")
    elif provider_id == "ollama" and not os.getenv("OLLAMA_API_KEY"):
        raise HTTPException(status_code=400, detail="Ollama API key not configured")
    elif provider_id == "gemini" and not os.getenv("GOOGLE_API_KEY"):
        raise HTTPException(status_code=400, detail="Google API key not configured")
    elif provider_id == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")

    # Determine model
    available_models = AVAILABLE_MODELS[provider_id]["models"]
    if request.model:
        if request.model not in available_models:
            raise HTTPException(
                status_code=400,
                detail=f"Model {request.model} not available for {provider_id}. "
                       f"Available: {available_models}"
            )
        model = request.model
    else:
        model = available_models[0]

    # Update environment (in-memory only, doesn't persist)
    os.environ["MODEL_PROVIDER"] = provider_id
    os.environ["MODEL_NAME"] = model

    # Clear any cached provider instances
    # ProviderFactory will create new instances on next call

    return {
        "success": True,
        "provider": provider_id,
        "model": model,
        "message": f"Provider switched to {AVAILABLE_MODELS[provider_id]['name']} with model {model}"
    }


@router.get("/models")
async def list_all_models():
    """List all available models across all providers."""
    current = get_current_provider_info()
    models = []

    for provider_id, info in AVAILABLE_MODELS.items():
        for model in info["models"]:
            models.append({
                "id": f"{provider_id}/{model}",
                "provider": provider_id,
                "provider_name": info["name"],
                "model": model,
                "current": (provider_id == current["provider"] and model == current["model"])
            })

    return {"models": models, "current": current}


@router.post("/{provider_id}/test", response_model=ProviderTestResponse)
async def test_provider(provider_id: str):
    """Test a provider by generating a simple response."""
    import time

    provider_id = provider_id.lower()

    if provider_id not in AVAILABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")

    try:
        start_time = time.time()

        # Create provider instance
        provider = ProviderFactory.create(provider=provider_id)

        # Test generation
        response = await provider.generate(
            "Say 'Hello! I am working correctly.' and nothing else.",
            max_tokens=50
        )

        latency_ms = (time.time() - start_time) * 1000

        return ProviderTestResponse(
            success=True,
            latency_ms=round(latency_ms, 2),
            test_output=response.content
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provider test failed: {str(e)}")


@router.get("/models/current")
async def get_current_model():
    """Get detailed info about current model."""
    current = get_current_provider_info()
    provider_info = AVAILABLE_MODELS.get(current["provider"], {})

    return {
        "provider": current["provider"],
        "provider_name": provider_info.get("name", current["provider"]),
        "model": current["model"],
        "config": current["config"],
        "all_models": provider_info.get("models", [])
    }
