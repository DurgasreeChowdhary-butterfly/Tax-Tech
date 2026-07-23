import pytest

from app.integrations.storage.base import StorageKeyError, StorageObjectNotFoundError
from app.integrations.storage.local_filesystem import LocalFilesystemStorage


@pytest.fixture()
def storage(tmp_path):
    return LocalFilesystemStorage(str(tmp_path / "docs"))


def test_save_read_exists_round_trip(storage):
    key = "filing-sessions/abc/doc1"
    assert storage.exists(key) is False

    storage.save(key, b"hello world")

    assert storage.exists(key) is True
    assert storage.read(key) == b"hello world"


def test_read_missing_key_raises(storage):
    with pytest.raises(StorageObjectNotFoundError):
        storage.read("filing-sessions/abc/does-not-exist")


def test_delete_removes_object(storage):
    key = "filing-sessions/abc/doc1"
    storage.save(key, b"content")
    storage.delete(key)
    assert storage.exists(key) is False


def test_delete_missing_key_is_a_safe_no_op(storage):
    storage.delete("filing-sessions/abc/never-existed")  # must not raise


@pytest.mark.parametrize(
    "bad_key",
    [
        "../outside",
        "a/../../outside",
        "/etc/passwd",
        "a/../../../etc/passwd",
        "  leading-space",
    ],
)
def test_path_traversal_and_unsafe_keys_are_rejected(storage, bad_key):
    with pytest.raises(StorageKeyError):
        storage.save(bad_key, b"content")


def test_key_cannot_escape_root_directory(tmp_path):
    root = tmp_path / "docs"
    storage = LocalFilesystemStorage(str(root))

    with pytest.raises(StorageKeyError):
        storage.save("../escaped.txt", b"malicious")

    # Confirm nothing was written outside the root.
    assert not (tmp_path / "escaped.txt").exists()
