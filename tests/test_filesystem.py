"""Unit tests for dvc_databricks.filesystem."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, call, patch

import pytest

from dvc_databricks.filesystem import (
    DatabricksVolumesFileSystem,
    _DatabricksVolumesFS,
    _WriteBuffer,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def inner_fs(mock_client):
    """Return a _DatabricksVolumesFS with a mocked WorkspaceClient.

    skip_instance_cache=True bypasses fsspec's class-level instance cache so
    each test gets a fresh object bound to its own mock_client.
    """
    with patch("dvc_databricks.filesystem.WorkspaceClient", return_value=mock_client):
        with patch("dvc_databricks.filesystem.Config"):
            return _DatabricksVolumesFS(skip_instance_cache=True)


def _make_dvfs(url="dbvol:///Volumes/cat/schema/vol"):
    """Instantiate DatabricksVolumesFileSystem with patched deps."""
    with patch("dvc_databricks.filesystem.WorkspaceClient"):
        with patch("dvc_databricks.filesystem.Config"):
            from dvc_objects.fs.base import FileSystem as _Base

            with patch.object(_Base, "__init__", return_value=None):
                return DatabricksVolumesFileSystem(url=url)


def _dir_entry(path, is_directory=False, size=0):
    e = MagicMock()
    e.path = path
    e.is_directory = is_directory
    e.file_size = size
    e.last_modified = None
    return e


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS._strip_protocol
# ---------------------------------------------------------------------------


class TestInnerFsStripProtocol:
    def test_strips_dbvol_prefix(self):
        result = _DatabricksVolumesFS._strip_protocol("dbvol:///Volumes/cat/s/vol/f")
        assert result == "/Volumes/cat/s/vol/f"

    def test_ensures_leading_slash_when_missing(self):
        result = _DatabricksVolumesFS._strip_protocol("Volumes/cat/s/vol/f")
        assert result.startswith("/")

    def test_already_absolute_path_unchanged(self):
        result = _DatabricksVolumesFS._strip_protocol("/Volumes/cat/s/vol/f")
        assert result == "/Volumes/cat/s/vol/f"

    def test_list_input_processes_each_element(self):
        result = _DatabricksVolumesFS._strip_protocol(
            ["dbvol:///a/b", "dbvol:///c/d"]
        )
        assert result == ["/a/b", "/c/d"]


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.ls
# ---------------------------------------------------------------------------


class TestInnerFsLs:
    def test_directory_listing_with_detail(self, inner_fs, mock_client):
        mock_client.files.list_directory_contents.return_value = [
            _dir_entry("/Volumes/v/file.csv", size=100),
            _dir_entry("/Volumes/v/sub/", is_directory=True),
        ]

        result = inner_fs.ls("/Volumes/v/")

        assert len(result) == 2
        assert result[0] == {
            "name": "/Volumes/v/file.csv",
            "type": "file",
            "size": 100,
            "last_modified": None,
        }
        assert result[1]["type"] == "directory"

    def test_directory_listing_without_detail(self, inner_fs, mock_client):
        mock_client.files.list_directory_contents.return_value = [
            _dir_entry("/Volumes/v/file.csv", size=50),
        ]

        result = inner_fs.ls("/Volumes/v/", detail=False)

        assert result == ["/Volumes/v/file.csv"]

    def test_falls_back_to_info_when_not_a_directory(self, inner_fs, mock_client):
        mock_client.files.list_directory_contents.side_effect = Exception("not a dir")
        mock_client.files.get_metadata.return_value = MagicMock(content_length=42)

        result = inner_fs.ls("/Volumes/v/file.csv")

        assert len(result) == 1
        assert result[0]["type"] == "file"
        assert result[0]["size"] == 42

    def test_raises_file_not_found_when_path_missing(self, inner_fs, mock_client):
        mock_client.files.list_directory_contents.side_effect = Exception("not found")
        mock_client.files.get_metadata.side_effect = Exception("not found")
        mock_client.files.get_directory_metadata.side_effect = Exception("not found")

        with pytest.raises(FileNotFoundError):
            inner_fs.ls("/Volumes/v/missing")

    def test_empty_directory_returns_empty_list(self, inner_fs, mock_client):
        mock_client.files.list_directory_contents.return_value = []

        result = inner_fs.ls("/Volumes/v/empty/")

        assert result == []


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.info
# ---------------------------------------------------------------------------


class TestInnerFsInfo:
    def test_file_info(self, inner_fs, mock_client):
        mock_client.files.get_metadata.return_value = MagicMock(content_length=512)

        result = inner_fs.info("/Volumes/v/file.csv")

        assert result == {"name": "/Volumes/v/file.csv", "type": "file", "size": 512}

    def test_file_with_none_content_length(self, inner_fs, mock_client):
        mock_client.files.get_metadata.return_value = MagicMock(content_length=None)

        result = inner_fs.info("/Volumes/v/file.csv")

        assert result["size"] == 0

    def test_directory_info(self, inner_fs, mock_client):
        mock_client.files.get_metadata.side_effect = Exception("is a directory")
        mock_client.files.get_directory_metadata.return_value = MagicMock()

        # _strip_protocol removes trailing slashes, so the returned name
        # does not have a trailing slash even if the input did.
        result = inner_fs.info("/Volumes/v/subdir/")

        assert result["type"] == "directory"
        assert result["size"] == 0
        assert result["name"] == "/Volumes/v/subdir"

    def test_not_found_raises(self, inner_fs, mock_client):
        mock_client.files.get_metadata.side_effect = Exception("not found")
        mock_client.files.get_directory_metadata.side_effect = Exception("not found")

        with pytest.raises(FileNotFoundError):
            inner_fs.info("/Volumes/v/missing")


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.exists
# ---------------------------------------------------------------------------


class TestInnerFsExists:
    def test_existing_file_returns_true(self, inner_fs, mock_client):
        mock_client.files.get_metadata.return_value = MagicMock(content_length=10)

        assert inner_fs.exists("/Volumes/v/file.csv") is True

    def test_missing_file_returns_false(self, inner_fs, mock_client):
        mock_client.files.get_metadata.side_effect = Exception("not found")
        mock_client.files.get_directory_metadata.side_effect = Exception("not found")

        assert inner_fs.exists("/Volumes/v/missing.csv") is False


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.mkdir / makedirs
# ---------------------------------------------------------------------------


class TestInnerFsMkdir:
    def test_mkdir_calls_create_directory(self, inner_fs, mock_client):
        inner_fs.mkdir("/Volumes/v/new_dir")

        mock_client.files.create_directory.assert_called_once_with("/Volumes/v/new_dir")

    def test_makedirs_calls_create_directory(self, inner_fs, mock_client):
        inner_fs.makedirs("/Volumes/v/new/nested/dir")

        mock_client.files.create_directory.assert_called_once_with(
            "/Volumes/v/new/nested/dir"
        )

    def test_makedirs_exist_ok_suppresses_exception(self, inner_fs, mock_client):
        mock_client.files.create_directory.side_effect = Exception("already exists")

        inner_fs.makedirs("/Volumes/v/existing", exist_ok=True)  # should not raise

    def test_makedirs_not_exist_ok_re_raises(self, inner_fs, mock_client):
        mock_client.files.create_directory.side_effect = Exception("already exists")

        with pytest.raises(Exception, match="already exists"):
            inner_fs.makedirs("/Volumes/v/existing", exist_ok=False)


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.rm / rm_file
# ---------------------------------------------------------------------------


class TestInnerFsRm:
    def test_rm_file_deletes_single_file(self, inner_fs, mock_client):
        mock_client.files.get_metadata.side_effect = Exception("not found")
        mock_client.files.get_directory_metadata.side_effect = Exception("not found")

        inner_fs.rm("/Volumes/v/file.csv")

        mock_client.files.delete.assert_called_once_with("/Volumes/v/file.csv")

    def test_rm_list_of_files(self, inner_fs, mock_client):
        mock_client.files.get_metadata.side_effect = Exception("not found")
        mock_client.files.get_directory_metadata.side_effect = Exception("not found")

        inner_fs.rm(["/Volumes/v/a.csv", "/Volumes/v/b.csv"])

        assert mock_client.files.delete.call_count == 2

    def test_rm_file_method(self, inner_fs, mock_client):
        inner_fs.rm_file("/Volumes/v/file.csv")

        mock_client.files.delete.assert_called_once_with("/Volumes/v/file.csv")


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS._open
# ---------------------------------------------------------------------------


class TestInnerFsOpen:
    def test_read_mode_returns_bytes_io(self, inner_fs, mock_client):
        mock_client.files.download.return_value = MagicMock(
            contents=io.BytesIO(b"hello world")
        )

        result = inner_fs._open("/Volumes/v/file.csv", mode="rb")

        assert isinstance(result, io.BytesIO)
        assert result.read() == b"hello world"

    def test_read_mode_raises_file_not_found(self, inner_fs, mock_client):
        mock_client.files.download.side_effect = Exception("not found: 404")

        with pytest.raises(FileNotFoundError):
            inner_fs._open("/Volumes/v/missing.csv", mode="rb")

    def test_read_mode_reraises_other_errors(self, inner_fs, mock_client):
        mock_client.files.download.side_effect = ConnectionError("timeout")

        with pytest.raises(ConnectionError):
            inner_fs._open("/Volumes/v/file.csv", mode="rb")

    def test_write_mode_returns_write_buffer(self, inner_fs, mock_client):
        result = inner_fs._open("/Volumes/v/file.csv", mode="wb")

        assert isinstance(result, _WriteBuffer)

    def test_unsupported_mode_raises_value_error(self, inner_fs, mock_client):
        with pytest.raises(ValueError, match="Unsupported mode"):
            inner_fs._open("/Volumes/v/file.csv", mode="a")


# ---------------------------------------------------------------------------
# _DatabricksVolumesFS.put_file / get_file
# ---------------------------------------------------------------------------


class TestInnerFsPutFile:
    def test_uploads_file_content(self, inner_fs, mock_client, tmp_path):
        local = tmp_path / "data.csv"
        local.write_bytes(b"col1,col2\n1,2\n")

        inner_fs.put_file(str(local), "/Volumes/v/data.csv")

        mock_client.files.upload.assert_called_once()
        path_arg = mock_client.files.upload.call_args[0][0]
        assert path_arg == "/Volumes/v/data.csv"
        assert mock_client.files.upload.call_args[1]["overwrite"] is True


class TestInnerFsGetFile:
    def test_downloads_to_local_path(self, inner_fs, mock_client, tmp_path):
        mock_client.files.download.return_value = MagicMock(
            contents=io.BytesIO(b"col1,col2\n1,2\n")
        )
        dest = tmp_path / "output.csv"

        inner_fs.get_file("/Volumes/v/data.csv", str(dest))

        assert dest.read_bytes() == b"col1,col2\n1,2\n"

    def test_downloads_to_outfile_object(self, inner_fs, mock_client):
        mock_client.files.download.return_value = MagicMock(
            contents=io.BytesIO(b"hello")
        )
        buf = io.BytesIO()

        inner_fs.get_file("/Volumes/v/data.csv", "/ignored/path", outfile=buf)

        assert buf.getvalue() == b"hello"

    def test_creates_intermediate_directories(self, inner_fs, mock_client, tmp_path):
        mock_client.files.download.return_value = MagicMock(
            contents=io.BytesIO(b"data")
        )
        dest = tmp_path / "a" / "b" / "c" / "output.csv"

        inner_fs.get_file("/Volumes/v/data.csv", str(dest))

        assert dest.exists()


# ---------------------------------------------------------------------------
# _WriteBuffer
# ---------------------------------------------------------------------------


class TestWriteBuffer:
    def test_write_and_close_triggers_upload(self, mock_client):
        buf = _WriteBuffer(mock_client, "/Volumes/v/file.csv")
        buf.write(b"hello world")
        buf.close()

        mock_client.files.upload.assert_called_once()
        path_arg = mock_client.files.upload.call_args[0][0]
        assert path_arg == "/Volumes/v/file.csv"

    def test_upload_contains_written_bytes(self, mock_client):
        buf = _WriteBuffer(mock_client, "/Volumes/v/file.csv")
        buf.write(b"line1\n")
        buf.write(b"line2\n")
        buf.close()

        uploaded_stream = mock_client.files.upload.call_args[0][1]
        assert uploaded_stream.read() == b"line1\nline2\n"

    def test_context_manager_triggers_upload(self, mock_client):
        with _WriteBuffer(mock_client, "/Volumes/v/file.csv") as buf:
            buf.write(b"data")

        mock_client.files.upload.assert_called_once()

    def test_close_is_idempotent(self, mock_client):
        buf = _WriteBuffer(mock_client, "/Volumes/v/file.csv")
        buf.write(b"data")
        buf.close()
        buf.close()

        assert mock_client.files.upload.call_count == 1

    def test_readable_returns_false(self, mock_client):
        buf = _WriteBuffer(mock_client, "/path")
        assert buf.readable() is False

    def test_writable_returns_true(self, mock_client):
        buf = _WriteBuffer(mock_client, "/path")
        assert buf.writable() is True

    def test_seekable_returns_false(self, mock_client):
        buf = _WriteBuffer(mock_client, "/path")
        assert buf.seekable() is False

    def test_overwrite_flag_is_true(self, mock_client):
        with _WriteBuffer(mock_client, "/Volumes/v/file.csv") as buf:
            buf.write(b"x")

        assert mock_client.files.upload.call_args[1]["overwrite"] is True


# ---------------------------------------------------------------------------
# DatabricksVolumesFileSystem
# ---------------------------------------------------------------------------


class TestDatabricksVolumesFileSystem:
    def test_strip_protocol_removes_dbvol_prefix(self):
        result = DatabricksVolumesFileSystem._strip_protocol(
            "dbvol:///Volumes/cat/s/vol/file"
        )
        assert result == "/Volumes/cat/s/vol/file"

    def test_strip_protocol_adds_leading_slash(self):
        result = DatabricksVolumesFileSystem._strip_protocol("Volumes/cat/s/vol/file")
        assert result.startswith("/")

    def test_strip_protocol_list_input(self):
        result = DatabricksVolumesFileSystem._strip_protocol(
            ["dbvol:///a", "dbvol:///b"]
        )
        assert result == ["/a", "/b"]

    def test_unstrip_protocol_adds_dbvol_prefix(self):
        dvfs = _make_dvfs()
        result = dvfs.unstrip_protocol("/Volumes/cat/s/vol/file")
        assert result == "dbvol:///Volumes/cat/s/vol/file"

    def test_get_kwargs_from_urls(self):
        url = "dbvol:///Volumes/cat/s/vol"
        result = DatabricksVolumesFileSystem._get_kwargs_from_urls(url)
        assert result == {"url": url}

    def test_fs_property_is_lazily_initialized(self):
        dvfs = _make_dvfs()
        assert dvfs._fs_instance is None

        with patch(
            "dvc_databricks.filesystem._DatabricksVolumesFS"
        ) as mock_inner_cls:
            _ = dvfs.fs
            mock_inner_cls.assert_called_once()

    def test_fs_property_returns_cached_instance(self):
        dvfs = _make_dvfs()

        with patch("dvc_databricks.filesystem._DatabricksVolumesFS"):
            fs1 = dvfs.fs
            fs2 = dvfs.fs

        assert fs1 is fs2

    def test_protocol_is_dbvol(self):
        assert DatabricksVolumesFileSystem.protocol == "dbvol"

    def test_param_checksum_is_md5(self):
        assert DatabricksVolumesFileSystem.PARAM_CHECKSUM == "md5"

    def test_requires_contains_databricks_sdk(self):
        assert "databricks-sdk" in DatabricksVolumesFileSystem.REQUIRES
        assert DatabricksVolumesFileSystem.REQUIRES["databricks-sdk"] == "databricks.sdk"
