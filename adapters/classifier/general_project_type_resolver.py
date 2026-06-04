"""ProjectTypeResolver implementation that always returns GENERAL."""

from __future__ import annotations

from core.domain.project import Project, ProjectType
from core.interfaces.project_type_resolver import ProjectTypeResolver


class GeneralProjectTypeResolver(ProjectTypeResolver):
    """v0.1 resolver: defer real classification to a later task."""

    def resolve(self, project: Project) -> str:
        return ProjectType.GENERAL.value
