# dvc-databricks

A [DVC](https://dvc.org) remote storage plugin that enables data versioning on **Databricks Unity Catalog Volumes**.

Store large data files on Databricks Volumes (backed by S3 or ADLS), keep only lightweight `.dvc` pointer files in your git repository, and use standard DVC commands — no custom code required.

```bash
dvc push   # uploads data to Databricks Volume via Databricks SDK
dvc pull   # downloads data from Databricks Volume
```

---

## Why this plugin?

Databricks Unity Catalog Volumes cannot be accessed like a plain S3 bucket — all I/O should go through the **Databricks Files API**. This plugin bridges DVC and the Databricks SDK so you can version and share datasets stored on Volumes without ever leaving the standard DVC workflow.

---

## Requirements

- Python >= 3.10
- [DVC](https://dvc.org/doc/install) >= 3.0
- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/install.html) configured with a profile in `~/.databrickscfg`
- Access to a Databricks Unity Catalog Volume

---

## Installation

```bash
pip install dvc-databricks
```

Once installed, the `dbvol://` remote protocol is automatically available to DVC in every process — no imports or additional configuration needed.

---

## Setup

### 1. Initialize DVC in your repository (if not already done)

```bash
dvc init
git add .dvc
git commit -m "initialize DVC"
```

### 2. Add the Databricks Volume as a DVC remote

```bash
dvc remote add -d myremote \
    dbvol:///Volumes/<catalog>/<schema>/<volume>/<path>
```

Example:

```bash
dvc remote add -d myremote \
    dbvol:///Volumes/ml_catalog/datasets/storage/dvc_cache
```

### 3. Set your Databricks profile

```bash
export DATABRICKS_CONFIG_PROFILE=<your-profile-name>
```

> **Note:** DVC remotes do not support arbitrary config keys, so the Databricks
> profile must be provided via this environment variable — it cannot be stored
> in `.dvc/config`. Add the export to your `~/.zshrc` or `~/.bashrc` to make
> it permanent.

---

## Usage

### Track a data file

```bash
dvc add data/dataset.csv
```

This creates `data/dataset.csv.dvc` — a small pointer file that goes into git.
The actual data file must listed in `.gitignore`.

### Push data to the Volume

```bash
dvc push
```

Uploads the file to your Databricks Volume via the Databricks SDK.

### Commit the pointer to git

```bash
git add data/dataset.csv.dvc .gitignore
git commit -m "track dataset v1 with DVC"
git push
```

### Pull data in another environment

```bash
git clone <your-repo>
pip install dvc-databricks
export DATABRICKS_CONFIG_PROFILE=<your-profile-name>
dvc pull
```

---

## CLI — `dvc-databricks add`

The `dvc-databricks add` command recursively finds files under a directory and tracks each one with DVC, creating **one `.dvc` pointer file per file**. The full folder structure is preserved in git, which allows granular pulls by file or subfolder — unlike DVC's built-in `dvc add <dir>`, which creates a single `.dvc` file for the whole directory.

### Syntax

```
dvc-databricks add <path> [--include EXT ...] [--exclude EXT ...]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `path` | Root directory to scan recursively (required). |
| `--include EXT ...` | **Whitelist** — only track files with these extensions. Accepts multiple values. |
| `--exclude EXT ...` | **Blacklist** — always skip files with these extensions. Accepts multiple values. Takes precedence over `--include`. |

Extensions can be written with or without a leading dot (`.csv` and `csv` are equivalent) and are matched case-insensitively.

### Filter logic

- `--include` is a **whitelist**: only files whose extension is in the list are tracked.
- `--exclude` is a **blacklist**: files whose extension is in the list are always skipped.
- When both are provided, `--exclude` takes precedence over `--include`.
- When neither is provided, **all files** are tracked.

### Examples

```bash
# Track only CSV and JSON files
dvc-databricks add /path/to/dataset --include .csv .json

# Track all files except macOS artifacts and temp files
dvc-databricks add /path/to/dataset --exclude .DS_Store .tmp .log

# Only CSVs, but skip .DS_Store even if --include .csv is set
dvc-databricks add /path/to/dataset --include .csv --exclude .DS_Store

# Track all files with no filters
dvc-databricks add /path/to/dataset
```

### After running

```bash
git add .
git commit -m "track dataset file by file"
dvc push
```

- One `.dvc` pointer file is created next to each tracked data file.
- Each directory containing tracked files gets a `.gitignore` that excludes the raw data files from git.
- `dvc push` uploads all tracked files to the configured Databricks Volume.

---

## How it works

```
Your git repo                   Databricks Volume (S3 / ADLS)
──────────────────              ───────────────────────────────────
data/dataset.csv.dvc  ──────►  /Volumes/catalog/schema/vol/
.dvc/config                     └── files/md5/
                                    ├── ab/cdef1234...   ← actual data
                                    └── 9f/123abc...     ← actual data
```

**`dvc|dvc-databricks add`** hashes the file and stores it in the local DVC cache (`.dvc/cache`).
A `.dvc` pointer file containing the MD5 hash is created next to your data file.

**`dvc push`** uploads from the local cache to the Volume using the Databricks
Files API (`WorkspaceClient.files.upload`). Files are stored content-addressed:
`<volume_path>/files/md5/<hash[:2]>/<hash[2:]>`.

**`dvc pull`** downloads from the Volume into the local cache, then restores
the file to its original path.

Only `.dvc` pointer files are ever committed to git — the data stays on the Volume.

---

## Architecture

The plugin follows the same pattern as official DVC plugins:

| Class | Base | Role |
|-------|------|------|
| `DatabricksVolumesFileSystem` | `dvc_objects.FileSystem` | DVC-facing layer: config, checksum strategy, dependency check |
| `_DatabricksVolumesFS` | `fsspec.AbstractFileSystem` | I/O layer: all Databricks SDK calls |

A `.pth` file installed into `site-packages` ensures the plugin is loaded at
Python startup in every process (including DVC CLI subprocesses), without
requiring any manual imports.

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABRICKS_CONFIG_PROFILE` | Databricks CLI profile name from `~/.databrickscfg`. Falls back to the default profile if not set. |

---

## License

[MIT](LICENSE) © Óscar Reyes
