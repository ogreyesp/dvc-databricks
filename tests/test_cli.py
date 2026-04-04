"""Unit tests for dvc_databricks.cli."""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dvc_databricks.cli import (
    _collect_files,
    _normalize_extensions,
    build_parser,
    cmd_add,
)


# ---------------------------------------------------------------------------
# _normalize_extensions
# ---------------------------------------------------------------------------


class TestNormalizeExtensions:
    def test_none_returns_empty_set(self):
        assert _normalize_extensions(None) == set()

    def test_empty_list_returns_empty_set(self):
        assert _normalize_extensions([]) == set()

    def test_extensions_with_dot(self):
        assert _normalize_extensions([".csv", ".json"]) == {".csv", ".json"}

    def test_extensions_without_dot(self):
        assert _normalize_extensions(["csv", "json"]) == {".csv", ".json"}

    def test_mixed_dot_and_no_dot(self):
        assert _normalize_extensions([".csv", "json"]) == {".csv", ".json"}

    def test_uppercase_normalized_to_lowercase(self):
        assert _normalize_extensions([".CSV", ".JSON"]) == {".csv", ".json"}

    def test_mixed_case_without_dot(self):
        assert _normalize_extensions(["CSV", "Json"]) == {".csv", ".json"}

    def test_single_extension(self):
        assert _normalize_extensions([".parquet"]) == {".parquet"}

    def test_deduplication(self):
        result = _normalize_extensions([".csv", ".CSV", "csv"])
        assert result == {".csv"}


# ---------------------------------------------------------------------------
# _collect_files
# ---------------------------------------------------------------------------


class TestCollectFiles:
    def test_no_filters_collects_all_files(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.json").write_text("data")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.parquet").write_text("data")

        result = _collect_files(tmp_path, set(), set())

        assert len(result) == 3

    def test_include_whitelist_keeps_only_matching(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.json").write_text("data")
        (tmp_path / "c.txt").write_text("data")

        result = _collect_files(tmp_path, {".csv"}, set())

        assert len(result) == 1
        assert result[0].suffix == ".csv"

    def test_include_multiple_extensions(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.json").write_text("data")
        (tmp_path / "c.txt").write_text("data")

        result = _collect_files(tmp_path, {".csv", ".json"}, set())

        assert len(result) == 2

    def test_exclude_blacklist_removes_matching(self, tmp_path):
        # Use a named extension so pathlib's .suffix picks it up correctly.
        # Note: ".DS_Store" dotfiles have no suffix — "data.DS_Store" does.
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "data.DS_Store").write_text("data")

        result = _collect_files(tmp_path, set(), {".ds_store"})

        assert len(result) == 1
        assert result[0].name == "a.csv"

    def test_exclude_takes_precedence_over_include(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")

        result = _collect_files(tmp_path, {".csv"}, {".csv"})

        assert result == []

    def test_returns_sorted_paths(self, tmp_path):
        (tmp_path / "z.csv").write_text("data")
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "m.csv").write_text("data")

        result = _collect_files(tmp_path, set(), set())
        names = [f.name for f in result]

        assert names == sorted(names)

    def test_skips_directories(self, tmp_path):
        (tmp_path / "subdir").mkdir()

        result = _collect_files(tmp_path, set(), set())

        assert result == []

    def test_recursive_collection(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.csv").write_text("data")

        result = _collect_files(tmp_path, set(), set())

        assert len(result) == 1

    def test_empty_directory_returns_empty(self, tmp_path):
        result = _collect_files(tmp_path, set(), set())
        assert result == []

    def test_extension_match_is_case_insensitive(self, tmp_path):
        (tmp_path / "DATA.CSV").write_text("data")

        result = _collect_files(tmp_path, {".csv"}, set())

        assert len(result) == 1

    def test_dotfile_excluded_by_name(self, tmp_path):
        (tmp_path / ".DS_Store").write_text("")
        (tmp_path / "data.csv").write_text("data")

        result = _collect_files(tmp_path, set(), {".ds_store"})

        assert [f.name for f in result] == ["data.csv"]

    def test_dotfile_not_collected_when_include_set(self, tmp_path):
        (tmp_path / ".DS_Store").write_text("")
        (tmp_path / "data.csv").write_text("data")

        result = _collect_files(tmp_path, {".csv"}, set())

        assert [f.name for f in result] == ["data.csv"]


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------


def _mock_repo():
    """Return a MagicMock that works as a context manager returning itself."""
    repo = MagicMock()
    repo.__enter__ = MagicMock(return_value=repo)
    repo.__exit__ = MagicMock(return_value=False)
    return repo


class TestCmdAdd:
    def test_nonexistent_path_exits(self, tmp_path):
        args = argparse.Namespace(
            path=str(tmp_path / "does_not_exist"),
            include=None,
            exclude=None,
        )
        with pytest.raises(SystemExit):
            cmd_add(args)

    def test_no_files_found_exits(self, tmp_path):
        args = argparse.Namespace(path=str(tmp_path), include=[".csv"], exclude=None)
        with pytest.raises(SystemExit):
            cmd_add(args)

    def test_identical_include_and_exclude_exits(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        args = argparse.Namespace(
            path=str(tmp_path), include=[".csv"], exclude=[".csv"]
        )
        with pytest.raises(SystemExit):
            cmd_add(args)

    def test_tracks_all_files_when_no_filters(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.json").write_text("data")
        args = argparse.Namespace(path=str(tmp_path), include=None, exclude=None)
        repo = _mock_repo()

        with patch("dvc.repo.Repo", return_value=repo):
            cmd_add(args)

        assert repo.add.call_count == 2

    def test_include_filter_limits_tracked_files(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.txt").write_text("data")
        args = argparse.Namespace(path=str(tmp_path), include=[".csv"], exclude=None)
        repo = _mock_repo()

        with patch("dvc.repo.Repo", return_value=repo):
            cmd_add(args)

        assert repo.add.call_count == 1
        called_path = repo.add.call_args[0][0][0]
        assert called_path.endswith(".csv")

    def test_exclude_filter_skips_files(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        (tmp_path / "b.tmp").write_text("data")
        args = argparse.Namespace(path=str(tmp_path), include=None, exclude=[".tmp"])
        repo = _mock_repo()

        with patch("dvc.repo.Repo", return_value=repo):
            cmd_add(args)

        assert repo.add.call_count == 1

    def test_each_file_is_added_individually(self, tmp_path):
        for name in ["a.csv", "b.csv", "c.csv"]:
            (tmp_path / name).write_text("data")
        args = argparse.Namespace(path=str(tmp_path), include=None, exclude=None)
        repo = _mock_repo()

        with patch("dvc.repo.Repo", return_value=repo):
            cmd_add(args)

        assert repo.add.call_count == 3

    def test_add_called_with_list_of_one_string(self, tmp_path):
        (tmp_path / "a.csv").write_text("data")
        args = argparse.Namespace(path=str(tmp_path), include=None, exclude=None)
        repo = _mock_repo()

        with patch("dvc.repo.Repo", return_value=repo):
            cmd_add(args)

        call_arg = repo.add.call_args[0][0]
        assert isinstance(call_arg, list)
        assert len(call_arg) == 1


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_add_command_requires_path(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/some/path"])
        assert args.path == "/some/path"

    def test_include_default_is_none(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/path"])
        assert args.include is None

    def test_exclude_default_is_none(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/path"])
        assert args.exclude is None

    def test_include_accepts_multiple_extensions(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/path", "--include", ".csv", ".json"])
        assert args.include == [".csv", ".json"]

    def test_exclude_accepts_multiple_extensions(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/path", "--exclude", ".tmp", ".log"])
        assert args.exclude == [".tmp", ".log"]

    def test_include_and_exclude_together(self):
        parser = build_parser()
        args = parser.parse_args(
            ["add", "/path", "--include", ".csv", "--exclude", ".DS_Store"]
        )
        assert args.include == [".csv"]
        assert args.exclude == [".DS_Store"]

    def test_no_command_exits(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_func_is_set_to_cmd_add(self):
        parser = build_parser()
        args = parser.parse_args(["add", "/path"])
        assert args.func is cmd_add
