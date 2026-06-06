import inspect

from api.dependencies import get_overview_service, get_upload_service
from features.ingest.upload_service import UploadService
from features.overview.overview_service import ProjectOverviewService


def test_service_constructors_accept_chunking_service() -> None:
    assert "chunking_service" in inspect.signature(UploadService).parameters
    assert "chunking_service" in inspect.signature(ProjectOverviewService).parameters


def test_dependencies_accept_chunking_service() -> None:
    assert "chunking_service" in inspect.signature(get_upload_service).parameters
    assert "chunking_service" in inspect.signature(get_overview_service).parameters
