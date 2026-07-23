from pathlib import Path, PurePosixPath

from app.integrations.storage.base import StorageKeyError, StorageObjectNotFoundError


class LocalFilesystemStorage:
    """Private storage adapter backed by a local directory. Never serves a
    public URL — files are only ever accessed by reading bytes through this
    class (see StorageProvider). Suitable for local development and tests;
    swap the factory in provider.py for an S3-compatible adapter later
    without touching any service/domain code.
    """

    def __init__(self, root_dir: str):
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        # Reject absolute paths and any ".." segment outright rather than
        # relying solely on the resolved-path containment check below —
        # defense in depth, and a clearer error for an obviously bad key.
        pure = PurePosixPath(key)
        if pure.is_absolute() or ".." in pure.parts or not key or key != key.strip():
            raise StorageKeyError(f"unsafe storage key: {key!r}")

        resolved = (self._root / pure).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            raise StorageKeyError(f"unsafe storage key: {key!r}") from None
        return resolved

    def save(self, key: str, content: bytes) -> None:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.is_file():
            raise StorageObjectNotFoundError(f"no storage object for key {key!r}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve_path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve_path(key)
        path.unlink(missing_ok=True)
