"""
Command-line interface for dvc-databricks.

Provides commands that extend DVC with Databricks-specific functionality.

Commands
--------
add
    Recursively track files in a directory with DVC, creating one .dvc pointer
    file per tracked file. Supports include/exclude extension filters.

Usage
-----
    # Track only CSV and JSON files
    dvc-databricks add /path/to/dataset --include .csv .json

    # Track everything except macOS artifacts and temp files
    dvc-databricks add /path/to/dataset --exclude .DS_Store .tmp .log

    # Combine both filters — only CSVs, skip .DS_Store
    dvc-databricks add /path/to/dataset --include .csv --exclude .DS_Store

    # Track all files (no filters)
    dvc-databricks add /path/to/dataset

Filter logic
------------
    - ``--include`` is a whitelist: only files with these extensions are tracked.
    - ``--exclude`` is a blacklist: files with these extensions are always skipped.
    - When both are provided, ``--exclude`` takes precedence over ``--include``.
    - When neither is provided, all files are tracked.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _normalize_extensions(exts: list[str] | None) -> set[str]:
    """Normalize a list of extensions to lowercase with a leading dot.

    Args:
        exts: Raw extension strings, e.g. ``["csv", ".JSON", ".tmp"]``.
            May be ``None`` if the argument was not provided.

    Returns:
        Set of normalized extensions, e.g. ``{".csv", ".json", ".tmp"}``.
    """
    if not exts:
        return set()
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}


def _collect_files(root: Path, include: set[str], exclude: set[str]) -> list[Path]:
    """Collect files under *root* applying include/exclude extension filters.

    Filter logic:
        - If ``include`` is non-empty, only files whose extension is in
          ``include`` are kept.
        - If ``exclude`` is non-empty, files whose extension is in ``exclude``
          are removed.
        - If both are empty, all files are collected.
        - ``exclude`` always takes precedence over ``include``.

    Args:
        root: Directory to scan recursively.
        include: Set of normalized extensions to include. Empty means all.
        exclude: Set of normalized extensions to exclude.

    Returns:
        Sorted list of matching ``Path`` objects.
    """
    files = []
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        ext = f.suffix.lower() if f.suffix else f.name.lower()
        if include and ext not in include:
            continue
        if ext in exclude:
            continue
        files.append(f)
    return sorted(files)


def cmd_add(args: argparse.Namespace) -> None:
    """Recursively track files with DVC, creating one .dvc file per tracked file.

    Applies include/exclude extension filters before tracking. Preserves the
    full folder structure in git, enabling granular pulls by file or subfolder.

    After running this command:
        - One ``.dvc`` pointer file is created next to each tracked file.
        - Each directory containing tracked files gets a ``.gitignore`` that
          excludes the actual data files.
        - Run ``git add . && git commit`` to save the pointers to git.
        - Run ``dvc push`` to upload data to the Databricks Volume.

    Args:
        args: Parsed CLI arguments with ``path``, ``include``, and ``exclude``
            attributes.
    """
    from dvc.repo import Repo

    root = Path(args.path).resolve()

    if not root.exists():
        sys.exit(f"ERROR: path does not exist: {root}")

    include = _normalize_extensions(args.include)
    exclude = _normalize_extensions(args.exclude)

    if include and exclude and include == exclude:
        sys.exit("ERROR: --include and --exclude cannot contain the same extensions.")

    files = _collect_files(root, include, exclude)
    total = len(files)

    if total == 0:
        filters = []
        if include:
            filters.append(f"include={sorted(include)}")
        if exclude:
            filters.append(f"exclude={sorted(exclude)}")
        hint = f" with filters: {', '.join(filters)}" if filters else ""
        sys.exit(f"No files found under {root}{hint}")

    print(f"Including extensions : {sorted(include) if include else 'all'}")
    if exclude:
        print(f"Excluding extensions : {sorted(exclude)}")
    print(f"Files to track       : {total}\n")

    with Repo() as repo:
        for i, f in enumerate(files, 1):
            repo.add([str(f)])
            print(f"[{i}/{total}] {f.relative_to(root)}")

    print(f"\nDone. {total} .dvc pointer files created.")
    print("\nNext steps:")
    print("  git add .")
    print("  git commit -m 'track dataset file by file'")
    print("  dvc push")


_ADD_DESCRIPTION = """\
Recursively find files under a directory and track each one with DVC,
creating one .dvc pointer file per file. Preserves the full folder
structure in git and enables granular pulls by file or subfolder.

FILTER LOGIC
  --include is a whitelist: only files with these extensions are tracked.
  --exclude is a blacklist: files with these extensions are always skipped.
  When both are provided, --exclude takes precedence over --include.
  When neither is provided, all files are tracked.

EXAMPLES
  Track only CSV and JSON files:
    dvc-databricks add /path/to/dataset --include .csv .json

  Track all files except macOS artifacts and temp files:
    dvc-databricks add /path/to/dataset --exclude .DS_Store .tmp .log

  Only CSVs, but skip .DS_Store even if --include .csv is set:
    dvc-databricks add /path/to/dataset --include .csv --exclude .DS_Store

  Track all files with no filters:
    dvc-databricks add /path/to/dataset

AFTER RUNNING
  git add .
  git commit -m "track dataset file by file"
  dvc push
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Configured ``ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        prog="dvc-databricks",
        description="DVC utilities for Databricks Unity Catalog Volumes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser(
        "add",
        help="Recursively track files with DVC (one .dvc file per tracked file).",
        description=_ADD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_parser.add_argument(
        "path",
        help="Root directory to scan recursively.",
    )
    add_parser.add_argument(
        "--include",
        nargs="+",
        metavar="EXT",
        default=None,
        help=(
            "Whitelist: only track files with these extensions. "
            "Accepts multiple values: --include .csv .json .parquet"
        ),
    )
    add_parser.add_argument(
        "--exclude",
        nargs="+",
        metavar="EXT",
        default=None,
        help=(
            "Blacklist: always skip files with these extensions. "
            "Accepts multiple values: --exclude .DS_Store .tmp .log "
            "Takes precedence over --include."
        ),
    )
    add_parser.set_defaults(func=cmd_add)

    return parser


def main() -> None:
    """Entry point for the ``dvc-databricks`` CLI command.

    Parses arguments and dispatches to the appropriate subcommand.
    """
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
