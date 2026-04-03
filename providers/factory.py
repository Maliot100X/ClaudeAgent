"""Provider factory for creating LLM provider instances."""

import os
from typing import Optional

from .base import BaseProvider, ProviderConfig, ProviderType
from .fireworks import FireworksProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider


class ProviderFactory:
    """Factory for creating LLM provider instances."""

    _providers = {
        ProviderType.FIREWORKS: FireworksProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.OPENAI: OpenAIProvider,
    }

    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[ProviderConfig] = None
    ) -> BaseProvider:
        """
        Create a provider instance.

        Args:
            provider: Provider type name (fireworks, gemini, ollama, openai)
            api_key: API key for the provider
            model: Model name to use
            base_url: Custom base URL for the API
            config: Pre-built ProviderConfig (overrides other args)

        Returns:
            Configured provider instance

        Raises:
            ValueError: If provider type is unknown
        """
        if config is None:
            # Determine provider type
            provider_str = provider or os.getenv("MODEL_PROVIDER", "fireworks")
            try:
                provider_type = ProviderType(provider_str.lower())
            except ValueError:
                available = [p.value for p in ProviderType]
                raise ValueError(
                    f"Unknown provider: {provider_str}. "
                    f"Available: {', '.join(available)}"
                )

            # Build config
            config = ProviderConfig(
                provider_type=provider_type,
                api_key=api_key,
                model=model or os.getenv("MODEL_NAME", "accounts/fireworks/routers/kimi-k2p5-turbo"),
                base_url=base_url,
                temperature=float(os.getenv("MODEL_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "4096")),
                timeout=int(os.getenv("MODEL_TIMEOUT", "60")),
            )

        # Get provider class
        provider_class = cls._providers.get(config.provider_type)
        if not provider_class:
            raise ValueError(f"No implementation for provider: {config.provider_type}")

        return provider_class(config)

    @classmethod
    def from_env(cls) -> BaseProvider:
        """Create provider from environment variables."""
        config = ProviderConfig.from_env()
        return cls.create(config=config)

    @classmethod
    def register_provider(
        cls,
        provider_type: ProviderType,
        provider_class: type
    ):
        """
        Register a custom provider implementation.

        Args:
            provider_type: Provider type enum
            provider_class: Provider class inheriting from BaseProvider
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def available_providers(cls) -> list:
        """Return list of available provider names."""
        return [p.value for p in cls._providers.keys()]


# Convenience function for quick provider creation
def get_provider(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> BaseProvider:
    """
    Get a provider instance with minimal configuration.

    Args:
        provider: Provider name (fireworks, gemini, ollama, openai)
        api_key: API key
        model: Model name

    Returns:
        Configured provider instance
    """
    return ProviderFactory.create(
        provider=provider,
        api_key=api_key,
        model=model
    )
