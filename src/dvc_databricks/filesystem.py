"""
DVC filesystem plugin for Databricks Unity Catalog Volumes.

Architecture:

  DatabricksVolumesFileSystem   ← dvc_objects.FileSystem subclass
      │                            DVC-facing layer: config parsing,
      │                            checksum strategy, plugin registration
      │
      └── self.fs               ← _DatabricksVolumesFS (fsspec.AbstractFileSystem)
                                   I/O layer: upload, download, list, delete
                                   via Databricks SDK Files API

When this package is installed, the ``dvc.plugins`` entry point registers
``DatabricksVolumesFileSystem`` under the ``dbvol`` protocol. DVC discovers
it automatically — no imports or manual configuration required.

Users configure the remote once:

    dvc remote add -d myremote dbvol:///Volumes/catalog/schema/volume/path
    export DATABRICKS_CONFIG_PROFILE=<profile>

Then use standard DVC commands as usual:

    dvc push / dvc pull / dvc status ...
"""

from __future__ import annotations

import io
import logging
import os
import threading
from typing import ClassVar

from databricks.sdk import WorkspaceClient
from databricks.sdk.config import Config
from dvc_objects.fs.base import FileSystem
from fsspec import AbstractFileSystem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inner fsspec filesystem — handles raw I/O via Databricks SDK
# ---------------------------------------------------------------------------


class _DatabricksVolumesFS(AbstractFileSystem):
    """fsspec filesystem that routes all I/O through the Databricks SDK Files API.

    This is the I/O layer used internally by ``DatabricksVolumesFileSystem``.
    It is not intended to be used directly by end users.

    Args:
        profile: Databricks CLI profile name from ``~/.databrickscfg``.
            When ``None``, the SDK reads ``DATABRICKS_CONFIG_PROFILE`` from
            the environment, then falls back to the default profile.
        **storage_options: Additional options forwarded to
            ``AbstractFileSystem.__init__``.
    """

    protocol = "dbvol"

    def __init__(self, profile: str | None = None, **storage_options):

        super().__init__(**storage_options)

        resolved = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
        cfg = Config(profile=resolved) if resolved else Config()
        self._client = WorkspaceClient(config=cfg)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        """Remove the ``dbvol://`` prefix and ensure a leading slash.

        Args:
            path: Raw path, possibly prefixed with ``dbvol://``. Also accepts
                a list of paths, in which case each element is processed.

        Returns:
            Absolute path string starting with ``/``, or a list of such
            strings when the input is a list.
        """
        if isinstance(path, list):
            return [cls._strip_protocol(p) for p in path]

        path = super()._strip_protocol(path)

        if not path.startswith("/"):
            path = "/" + path

        return path

    # ------------------------------------------------------------------
    # Metadata operations
    # ------------------------------------------------------------------

    def ls(self, path: str, detail: bool = True, **kwargs):
        """List a directory or return a single-item list for a file.

        Tries the path as a directory first; falls back to ``info()`` if the
        directory listing raises an exception (i.e. path is a file).

        Args:
            path: Absolute Volume path to list.
            detail: If ``True``, return a list of dicts with keys
                ``name``, ``type``, ``size``, and ``last_modified``.
                If ``False``, return a list of path strings.
            **kwargs: Ignored; present for fsspec compatibility.

        Returns:
            List of dicts (when ``detail=True``) or list of path strings
            (when ``detail=False``).

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path = self._strip_protocol(path)

        try:
            entries = list(self._client.files.list_directory_contents(path))
            result = []

            for entry in entries:
                info = {
                    "name": entry.path,
                    "type": "directory" if entry.is_directory else "file",
                    "size": entry.file_size or 0,
                    "last_modified": entry.last_modified,
                }
                result.append(info if detail else entry.path)

            return result

        except Exception:
            pass

        # Fall back to a single-file lookup via info() to avoid duplicating
        # the metadata retrieval logic.
        info = self.info(path)  # raises FileNotFoundError if path does not exist
        return [info] if detail else [info["name"]]

    def info(self, path: str, **kwargs) -> dict:
        """Return metadata for a single file or directory.

        Tries a file metadata lookup first (cheaper), then falls back to a
        directory metadata lookup.

        Args:
            path: Absolute Volume path.
            **kwargs: Ignored; present for fsspec compatibility.

        Returns:
            Dict with keys ``name`` (str), ``type`` (``"file"`` or
            ``"directory"``), and ``size`` (int, bytes).

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path = self._strip_protocol(path)

        try:
            meta = self._client.files.get_metadata(path)

            return {"name": path, "type": "file", "size": meta.content_length or 0}
        except Exception:
            pass

        try:
            self._client.files.get_directory_metadata(path)

            return {"name": path, "type": "directory", "size": 0}
        except Exception:
            raise FileNotFoundError(f"No such file or directory: {path!r}")

    def exists(self, path: str, **kwargs) -> bool:
        """Return ``True`` if *path* exists on the Volume, ``False`` otherwise.

        Args:
            path: Absolute Volume path to check.
            **kwargs: Ignored; present for fsspec compatibility.

        Returns:
            ``True`` if the path exists, ``False`` if not.
        """
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False

    # ------------------------------------------------------------------
    # Directory operations
    # ------------------------------------------------------------------

    def mkdir(self, path: str, create_parents: bool = True, **kwargs):
        """Create a directory on the Volume.

        Args:
            path: Absolute Volume path for the new directory.
            create_parents: Ignored — the Databricks Files API always
                creates intermediate directories automatically.
            **kwargs: Ignored; present for fsspec compatibility.
        """
        path = self._strip_protocol(path)
        self._client.files.create_directory(path)

    def makedirs(self, path: str, exist_ok: bool = False):
        """Create a directory and all intermediate parents.

        Args:
            path: Absolute Volume path for the new directory.
            exist_ok: If ``False``, re-raises any exception thrown by the
                API. If ``True``, suppresses those exceptions.
        """
        path = self._strip_protocol(path)
        try:
            self._client.files.create_directory(path)
        except Exception:
            if not exist_ok:
                raise

    def rm_file(self, path: str):
        """Delete a single file from the Volume.

        Args:
            path: Absolute Volume path of the file to delete.
        """
        path = self._strip_protocol(path)
        self._client.files.delete(path)

    def rm(self, path, recursive: bool = False, **kwargs):
        """Delete one or more files or directories from the Volume.

        Args:
            path: Absolute Volume path (str) or list of paths to delete.
            recursive: If ``True``, recursively delete directory contents
                before deleting the directory itself.
            **kwargs: Ignored; present for fsspec compatibility.
        """
        paths = path if isinstance(path, list) else [path]

        for p in paths:
            p = self._strip_protocol(p)

            if recursive and self.isdir(p):

                for entry in self.ls(p, detail=True):
                    self.rm(entry["name"], recursive=True)
            else:
                self._client.files.delete(p)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _open(self, path: str, mode: str = "rb", **kwargs):
        """Open a file on the Volume for reading or writing.

        For reads, the file is downloaded eagerly into a ``BytesIO`` buffer.
        For writes, a ``_WriteBuffer`` is returned which uploads on ``close()``.

        Args:
            path: Absolute Volume path.
            mode: ``"rb"`` for reading or ``"wb"`` for writing.
            **kwargs: Ignored; present for fsspec compatibility.

        Returns:
            A ``BytesIO`` instance (read mode) or a ``_WriteBuffer``
            instance (write mode).

        Raises:
            ValueError: If *mode* is neither ``"rb"`` nor ``"wb"``.
        """
        path = self._strip_protocol(path)

        if "r" in mode:
            try:
                response = self._client.files.download(path)
                return io.BytesIO(response.contents.read())
            except Exception as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    raise FileNotFoundError(f"No such file: {path!r}") from e
                raise

        if "w" in mode:
            return _WriteBuffer(self._client, path)

        raise ValueError(f"Unsupported mode: {mode!r}")

    def put_file(self, lpath: str, rpath: str, **kwargs):
        """Upload a single local file to the Volume.

        Args:
            lpath: Absolute local filesystem path of the source file.
            rpath: Absolute Volume path of the destination.
            **kwargs: Ignored; present for fsspec compatibility.
        """
        rpath = self._strip_protocol(rpath)

        with open(lpath, "rb") as fh:
            self._client.files.upload(rpath, fh, overwrite=True)

    def get_file(self, rpath: str, lpath: str, outfile=None, **kwargs):
        """Download a single file from the Volume to a local path.

        Args:
            rpath: Absolute Volume path of the source file.
            lpath: Absolute local filesystem path of the destination.
                Intermediate directories are created automatically.
            outfile: If provided, write the downloaded bytes into this
                file-like object instead of saving to *lpath*.
            **kwargs: Ignored; present for fsspec compatibility.
        """
        rpath = self._strip_protocol(rpath)
        response = self._client.files.download(rpath)

        if outfile is not None:
            outfile.write(response.contents.read())
        else:
            os.makedirs(os.path.dirname(os.path.abspath(lpath)), exist_ok=True)

            with open(lpath, "wb") as fh:
                fh.write(response.contents.read())


class _WriteBuffer(io.RawIOBase):
    """Write-only in-memory buffer that uploads to Databricks on ``close()``.

    fsspec's ``_open(mode="wb")`` contract expects a file-like object.
    Because the Databricks Files API requires the full content to be
    available at upload time (it is not a streaming multipart API), we
    accumulate all ``write()`` calls in a ``BytesIO`` buffer and perform
    a single ``files.upload()`` call when the buffer is closed.

    The upload is triggered exactly once, either by an explicit ``close()``
    call or when used as a context manager (``with fs.open(path, "wb") as f``).

    Example:
        >>> with fs.open("/Volumes/catalog/schema/vol/file.csv", "wb") as f:
        ...     f.write(b"col1,col2\\n1,2\\n")
    """

    def __init__(self, client, path: str):
        """Initialize the buffer.

        Args:
            client: An authenticated ``WorkspaceClient`` instance.
            path: Absolute Volume path where the file will be written,
                e.g. ``/Volumes/catalog/schema/volume/subdir/file.csv``.
        """
        self._client = client
        self._path = path
        self._buf = io.BytesIO()

    def write(self, data: bytes) -> int:
        """Append *data* to the in-memory buffer.

        No network call is made at this point.

        Args:
            data: Bytes to buffer.

        Returns:
            Number of bytes written.
        """
        return self._buf.write(data)

    def close(self):
        """Flush the buffer to the Databricks Volume and close the stream.

        Performs a single ``files.upload()`` call with the accumulated
        buffer contents. Subsequent calls are no-ops (guarded by
        ``self.closed``).
        """
        if not self.closed:
            self._buf.seek(0)
            self._client.files.upload(self._path, self._buf, overwrite=True)

        super().close()

    def readable(self) -> bool:
        """Return ``False`` — this stream is write-only.

        Returns:
            Always ``False``.
        """
        return False

    def writable(self) -> bool:
        """Return ``True`` — this stream accepts ``write()`` calls.

        Returns:
            Always ``True``.
        """
        return True

    def seekable(self) -> bool:
        """Return ``False`` — seeking is not supported on the public interface.

        The internal ``BytesIO`` buffer is seeked internally by ``close()``
        before uploading, but callers must not rely on seek support.

        Returns:
            Always ``False``.
        """
        return False

    def __enter__(self):
        """Return *self* to support usage as a context manager.

        Returns:
            This ``_WriteBuffer`` instance.
        """
        return self

    def __exit__(self, *args):
        """Close the buffer and trigger the upload on context manager exit.

        Args:
            *args: Exception info (type, value, traceback) — ignored.
        """
        self.close()


# ---------------------------------------------------------------------------
# DVC plugin — dvc_objects.FileSystem wrapper
# ---------------------------------------------------------------------------


class DatabricksVolumesFileSystem(FileSystem):
    """DVC remote filesystem backed by Databricks Unity Catalog Volumes.

    Extends ``dvc_objects.fs.base.FileSystem``.

    DVC delegates all storage operations to ``self.fs`` (a
    ``_DatabricksVolumesFS`` instance), which communicates with the
    Databricks Volume via the SDK Files API — no direct S3 access.

    Configuration (one-time setup per repo):

        dvc remote add -d myremote \\
            dbvol:///Volumes/catalog/schema/volume/dvc_cache
        export DATABRICKS_CONFIG_PROFILE=<profile>

    After that, standard DVC commands work without any code changes:

        dvc push / dvc pull / dvc status

    Note:
        ``DATABRICKS_CONFIG_PROFILE`` must be set in the environment because
        DVC remotes do not support arbitrary config keys. The profile cannot
        be stored in ``.dvc/config``.
    """

    protocol = "dbvol"
    PARAM_CHECKSUM = "md5"
    # Format: {"pip_package_name": "importable.module.name"}
    # dvc_objects calls find_spec() on the value to check the dep is installed.
    REQUIRES: ClassVar[dict[str, str]] = {"databricks-sdk": "databricks.sdk"}

    def __init__(self, **config):
        """Parse DVC remote config and prepare the filesystem.

        Args:
            **config: DVC remote configuration dict. Expected keys:

                - ``url`` (str): Full remote URL, e.g.
                  ``dbvol:///Volumes/catalog/schema/volume/path``.
                - ``profile`` (str, optional): Databricks CLI profile name.
                  Falls back to ``DATABRICKS_CONFIG_PROFILE`` env var.
        """
        super().__init__(**config)
        self.url = config["url"]
        self._profile = config.get("profile") or os.environ.get(
            "DATABRICKS_CONFIG_PROFILE"
        )
        self._fs_instance: _DatabricksVolumesFS | None = None
        self._fs_lock = threading.RLock()

    @staticmethod
    def _get_kwargs_from_urls(urlpath: str) -> dict:
        """Extract constructor kwargs from a remote URL.

        Called by DVC when parsing ``dvc remote add`` URLs. Returns the
        URL as-is so it can be forwarded to ``__init__`` as ``config["url"]``.

        Args:
            urlpath: Full remote URL, e.g.
                ``dbvol:///Volumes/catalog/schema/volume/path``.

        Returns:
            Dict with a single ``url`` key.
        """
        return {"url": urlpath}

    @classmethod
    def _strip_protocol(cls, path: str) -> str:
        """Remove the ``dbvol://`` prefix and ensure a leading slash.

        Args:
            path: Raw path, possibly prefixed with ``dbvol://``.

        Returns:
            Absolute path string starting with ``/``.
        """
        if isinstance(path, list):
            return [cls._strip_protocol(p) for p in path]

        if path.startswith("dbvol://"):
            path = path[len("dbvol://") :]

        if not path.startswith("/"):
            path = "/" + path

        return path

    def unstrip_protocol(self, path: str) -> str:
        """Reconstruct the full ``dbvol://`` URL from an absolute path.

        Args:
            path: Absolute Volume path, e.g.
                ``/Volumes/catalog/schema/volume/file``.

        Returns:
            Full URL string, e.g.
            ``dbvol:///Volumes/catalog/schema/volume/file``.
        """
        return f"dbvol://{path}"

    @property
    def fs(self) -> _DatabricksVolumesFS:
        """Return the underlying fsspec filesystem, created lazily and cached.

        Thread-safe: uses an ``RLock`` to ensure only one instance is created
        even under concurrent access.

        Returns:
            A ``_DatabricksVolumesFS`` instance authenticated with the
            configured Databricks profile.
        """
        with self._fs_lock:
            if self._fs_instance is None:
                self._fs_instance = _DatabricksVolumesFS(profile=self._profile)

        return self._fs_instance
