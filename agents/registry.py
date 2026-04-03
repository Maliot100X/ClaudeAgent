"""Agent skill registry."""

from typing import Any, Dict, List, Optional, Type
import importlib
import inspect

from .base import BaseSkill


class SkillRegistry:
    """Registry for agent skills."""

    def __init__(self):
        self._skills: Dict[str, Type[BaseSkill]] = {}
        self._instances: Dict[str, BaseSkill] = {}

    def register(
        self,
        name: str,
        skill_class: Type[BaseSkill]
    ) -> None:
        """
        Register a skill class.

        Args:
            name: Skill name
            skill_class: Skill class to register
        """
        if not issubclass(skill_class, BaseSkill):
            raise ValueError(f"Skill must inherit from BaseSkill: {skill_class}")

        self._skills[name] = skill_class

    def unregister(self, name: str) -> None:
        """Unregister a skill."""
        if name in self._skills:
            del self._skills[name]
        if name in self._instances:
            del self._instances[name]

    def get(self, name: str) -> Optional[Type[BaseSkill]]:
        """Get a skill class by name."""
        return self._skills.get(name)

    def create(
        self,
        name: str,
        **kwargs
    ) -> Optional[BaseSkill]:
        """
        Create a skill instance.

        Args:
            name: Skill name
            **kwargs: Constructor arguments

        Returns:
            Skill instance or None
        """
        skill_class = self.get(name)
        if not skill_class:
            return None

        instance = skill_class(**kwargs)
        self._instances[name] = instance
        return instance

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a skill."""
        skill_class = self.get(name)
        if not skill_class:
            return None

        # Create temp instance to get metadata
        try:
            temp = skill_class()
            return {
                "name": temp.name,
                "description": temp.description,
                "parameters": temp.parameters,
                "class": skill_class.__name__,
                "module": skill_class.__module__
            }
        except:
            return {
                "name": name,
                "class": skill_class.__name__,
                "module": skill_class.__module__
            }

    def load_from_module(
        self,
        module_path: str
    ) -> List[str]:
        """
        Load all skills from a module.

        Args:
            module_path: Python module path (e.g., 'skills.market_data')

        Returns:
            List of loaded skill names
        """
        loaded = []

        try:
            module = importlib.import_module(module_path)

            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj)
                    and issubclass(obj, BaseSkill)
                    and obj != BaseSkill):
                    skill_name = getattr(obj, 'name', name.lower())
                    self.register(skill_name, obj)
                    loaded.append(skill_name)

        except Exception as e:
            print(f"Error loading skills from {module_path}: {e}")

        return loaded

    def create_batch(
        self,
        skill_names: List[str],
        **common_kwargs
    ) -> Dict[str, BaseSkill]:
        """
        Create multiple skill instances.

        Args:
            skill_names: List of skill names
            **common_kwargs: Arguments for all skills

        Returns:
            Dictionary of name -> skill instance
        """
        instances = {}

        for name in skill_names:
            skill = self.create(name, **common_kwargs)
            if skill:
                instances[name] = skill

        return instances


# Global registry instance
_global_registry: Optional[SkillRegistry] = None


def get_global_registry() -> SkillRegistry:
    """Get or create global skill registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def register_skill(
    name: str,
    skill_class: Type[BaseSkill]
) -> None:
    """Register a skill with the global registry."""
    registry = get_global_registry()
    registry.register(name, skill_class)


def get_skill(name: str) -> Optional[Type[BaseSkill]]:
    """Get a skill from the global registry."""
    registry = get_global_registry()
    return registry.get(name)


def create_skill(name: str, **kwargs) -> Optional[BaseSkill]:
    """Create a skill instance from the global registry."""
    registry = get_global_registry()
    return registry.create(name, **kwargs)
