CLI Reference
=============

``dvc-databricks add``
----------------------

Recursively finds files under a directory and tracks each one with DVC, creating
**one** ``.dvc`` **pointer file per file**. The full folder structure is preserved
in git, enabling granular pulls by file or subfolder.

This differs from the built-in ``dvc add <dir>``, which creates a single ``.dvc``
file for the entire directory — making it impossible to pull individual files later.

Syntax
^^^^^^

.. code-block:: text

   dvc-databricks add <path> [--include EXT ...] [--exclude EXT ...]

Arguments
^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Argument
     - Description
   * - ``path``
     - Root directory to scan recursively (required).
   * - ``--include EXT ...``
     - **Whitelist** — only track files with these extensions. Accepts multiple values.
   * - ``--exclude EXT ...``
     - **Blacklist** — always skip files with these extensions. Accepts multiple values. Takes precedence over ``--include``.

Extensions can be written with or without a leading dot (``.csv`` and ``csv`` are
equivalent) and are matched case-insensitively.

Filter logic
^^^^^^^^^^^^

- ``--include`` is a whitelist: only files whose extension is in the list are tracked.
- ``--exclude`` is a blacklist: files whose extension is in the list are always skipped.
- When both are provided, ``--exclude`` takes precedence over ``--include``.
- When neither is provided, **all files** are tracked.

Examples
^^^^^^^^

Track only CSV and JSON files:

.. code-block:: bash

   dvc-databricks add /path/to/dataset --include .csv .json

Track all files except macOS artifacts and temp files:

.. code-block:: bash

   dvc-databricks add /path/to/dataset --exclude .DS_Store .tmp .log

Only CSVs, but skip ``.DS_Store`` even if ``--include .csv`` is set:

.. code-block:: bash

   dvc-databricks add /path/to/dataset --include .csv --exclude .DS_Store

Track all files with no filters:

.. code-block:: bash

   dvc-databricks add /path/to/dataset

After running
^^^^^^^^^^^^^

.. code-block:: bash

   git add .
   git commit -m "track dataset file by file"
   dvc push

One ``.dvc`` pointer file is created next to each tracked data file. Each directory
containing tracked files gets a ``.gitignore`` that excludes the raw data files from
git. ``dvc push`` uploads all tracked files to the configured Databricks Volume.
