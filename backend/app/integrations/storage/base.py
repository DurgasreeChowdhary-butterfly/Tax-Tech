from typing import Protocol


class StorageKeyError(ValueError):
    """Raised when a storage key is unsafe (path traversal, absolute path, etc.)."""


class StorageObjectNotFoundError(FileNotFoundError):
    """Raised when a read/delete is attempted against a key with no backing object."""


class StorageProvider(Protocol):
    """Private object storage abstraction. No method here ever returns a public
    or signed URL — callers get bytes back directly, always backend-mediated.

    Implementations must reject unsafe keys (path traversal, absolute paths)
    rather than silently normalizing them.
    """

    def save(self, key: str, content: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...
