"""Skill registry and loader for integrating external skills."""

import os
import yaml
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import importlib.util

logger = logging.getLogger(__name__)


@dataclass
class SkillEndpoint:
    """Definition of a skill endpoint."""
    name: str
    method: str
    path: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    handler: Optional[Callable] = None


@dataclass
class Skill:
    """A registered skill with its configuration."""
    name: str
    version: str
    description: str
    author: str
    keywords: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    endpoints: List[SkillEndpoint] = field(default_factory=list)
    module_path: Optional[str] = None
    loaded: bool = False


class SkillRegistry:
    """
    Registry for loading and managing skills.

    Supports skills from:
    - Local skill definitions (YAML files)
    - GitHub repositories
    - skills.sh registry
    - cryptoskill.org registry
    """

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.skill_dir = Path(__file__).parent
        self._load_local_skills()

    def _load_local_skills(self):
        """Load skills from local skill directory."""
        for skill_path in self.skill_dir.iterdir():
            if skill_path.is_dir() and (skill_path / "skill.yaml").exists():
                self._load_skill_from_yaml(skill_path / "skill.yaml")

    def _load_skill_from_yaml(self, yaml_path: Path) -> Optional[Skill]:
        """Load a skill from its YAML definition."""
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            endpoints = []
            for ep_name, ep_data in data.get('endpoints', {}).items():
                endpoints.append(SkillEndpoint(
                    name=ep_name,
                    method=ep_data.get('method', 'GET'),
                    path=ep_data.get('path', '/'),
                    description=ep_data.get('description', ''),
                    parameters=ep_data.get('parameters', {})
                ))

            skill = Skill(
                name=data.get('name', yaml_path.parent.name),
                version=data.get('version', '1.0.0'),
                description=data.get('description', ''),
                author=data.get('author', 'Unknown'),
                keywords=data.get('keywords', []),
                config=data.get('configuration', {}),
                endpoints=endpoints,
                module_path=str(yaml_path.parent)
            )

            self.skills[skill.name] = skill
            logger.info(f"Loaded skill: {skill.name} v{skill.version}")
            return skill

        except Exception as e:
            logger.error(f"Failed to load skill from {yaml_path}: {e}")
            return None

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self.skills.get(name)

    def list_skills(self) -> List[Skill]:
        """List all registered skills."""
        return list(self.skills.values())

    def search_skills(self, keyword: str) -> List[Skill]:
        """Search skills by keyword."""
        results = []
        keyword_lower = keyword.lower()
        for skill in self.skills.values():
            if (keyword_lower in skill.name.lower() or
                keyword_lower in skill.description.lower() or
                any(keyword_lower in k.lower() for k in skill.keywords)):
                results.append(skill)
        return results

    def register_skill(self, skill: Skill):
        """Register a skill manually."""
        self.skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def load_skill_from_github(self, repo_url: str, skill_name: Optional[str] = None) -> Optional[Skill]:
        """
        Load a skill from a GitHub repository.

        Args:
            repo_url: GitHub repository URL or owner/repo format
            skill_name: Optional name to register as

        Returns:
            Loaded Skill or None
        """
        import subprocess
        import tempfile

        try:
            # Create temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone repository
                if not repo_url.startswith('http'):
                    repo_url = f"https://github.com/{repo_url}"

                logger.info(f"Cloning skill repo: {repo_url}")
                result = subprocess.run(
                    ['git', 'clone', '--depth', '1', repo_url, tmpdir],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    logger.error(f"Failed to clone: {result.stderr}")
                    return None

                # Look for skill.yaml
                skill_yaml = Path(tmpdir) / "skill.yaml"
                if not skill_yaml.exists():
                    # Try common locations
                    for subdir in Path(tmpdir).iterdir():
                        if subdir.is_dir():
                            candidate = subdir / "skill.yaml"
                            if candidate.exists():
                                skill_yaml = candidate
                                break

                if skill_yaml.exists():
                    skill = self._load_skill_from_yaml(skill_yaml)
                    if skill and skill_name:
                        skill.name = skill_name
                    return skill
                else:
                    logger.error(f"No skill.yaml found in {repo_url}")
                    return None

        except Exception as e:
            logger.error(f"Failed to load skill from GitHub: {e}")
            return None

    def load_crypto_skills(self) -> List[Skill]:
        """Load crypto/blockchain related skills from common registries."""
        loaded = []

        # Common crypto skill repositories to try
        crypto_repos = [
            # Solana ecosystem
            "solana-foundation/solana-web3.js",
            # Trading skills
            "quicknode-labs/blockchain-skills",
        ]

        for repo in crypto_repos:
            try:
                skill = self.load_skill_from_github(repo)
                if skill:
                    loaded.append(skill)
            except Exception as e:
                logger.warning(f"Could not load {repo}: {e}")

        return loaded

    def get_skill_config(self, skill_name: str) -> Dict[str, Any]:
        """Get configuration for a skill from environment variables."""
        skill = self.skills.get(skill_name)
        if not skill:
            return {}

        config = {}
        for key, spec in skill.config.items():
            env_key = f"{skill_name.upper()}_{key.upper()}"
            value = os.getenv(env_key)

            if value is None and spec.get('required'):
                logger.warning(f"Required config {key} not set for {skill_name}")

            if value is not None:
                # Type conversion
                if spec.get('type') == 'integer':
                    value = int(value)
                elif spec.get('type') == 'boolean':
                    value = value.lower() in ('true', '1', 'yes')

            config[key] = value

        return config

    def initialize_skill(self, skill_name: str) -> bool:
        """Initialize a skill with its configuration."""
        skill = self.skills.get(skill_name)
        if not skill:
            logger.error(f"Skill not found: {skill_name}")
            return False

        try:
            config = self.get_skill_config(skill_name)

            # Load Python module if exists
            init_file = Path(skill.module_path) / "__init__.py"
            if init_file.exists():
                spec = importlib.util.spec_from_file_location(
                    skill_name,
                    init_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Look for initialize function
                    if hasattr(module, 'initialize'):
                        module.initialize(config)

                    # Bind endpoint handlers
                    for endpoint in skill.endpoints:
                        handler_name = f"handle_{endpoint.name}"
                        if hasattr(module, handler_name):
                            endpoint.handler = getattr(module, handler_name)

            skill.loaded = True
            logger.info(f"Initialized skill: {skill_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize skill {skill_name}: {e}")
            return False

    def call_skill_endpoint(
        self,
        skill_name: str,
        endpoint_name: str,
        **kwargs
    ) -> Any:
        """Call a skill endpoint."""
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")

        endpoint = None
        for ep in skill.endpoints:
            if ep.name == endpoint_name:
                endpoint = ep
                break

        if not endpoint:
            raise ValueError(f"Endpoint not found: {endpoint_name}")

        if not endpoint.handler:
            raise RuntimeError(f"Endpoint {endpoint_name} has no handler")

        return endpoint.handler(**kwargs)


# Global registry instance
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def reload_skills():
    """Reload all skills from disk."""
    global _registry
    _registry = SkillRegistry()
    logger.info("Skills reloaded")
