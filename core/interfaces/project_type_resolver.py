"""Project type policy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.domain.project import Project


class ProjectTypeResolver(ABC):
    """Resolve the project type hint passed to the overview prompt."""

    @abstractmethod
    def resolve(self, project: Project) -> str:
        """Return a project type value for ``project``."""
        ...
