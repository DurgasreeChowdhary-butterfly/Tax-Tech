from functools import lru_cache

from app.core.config import get_settings
from app.integrations.storage.base import StorageProvider
from app.integrations.storage.local_filesystem import LocalFilesystemStorage


@lru_cache
def get_storage_provider() -> StorageProvider:
    """Single seam for swapping storage backends. Only a local filesystem
    adapter exists today; an S3-compatible adapter can be added later by
    returning it here instead — no service/domain code would need to change.
    """
    settings = get_settings()
    return LocalFilesystemStorage(settings.document_storage_root)
