Usage
=====

Setup
-----

1. Initialize DVC in your repository (if not already done):

   .. code-block:: bash

      dvc init
      git add .dvc
      git commit -m "initialize DVC"

2. Add the Databricks Volume as a DVC remote:

   .. code-block:: bash

      dvc remote add -d myremote \
          dbvol:///Volumes/<catalog>/<schema>/<volume>/<path>

3. Set your Databricks profile:

   .. code-block:: bash

      export DATABRICKS_CONFIG_PROFILE=<your-profile-name>

   .. note::

      DVC remotes do not support arbitrary config keys, so the Databricks profile
      must be provided via this environment variable — it cannot be stored in
      ``.dvc/config``. Add the export to your ``~/.zshrc`` or ``~/.bashrc`` to make
      it permanent.

Standard DVC workflow
---------------------

Track a data file:

.. code-block:: bash

   dvc add data/dataset.csv

Push data to the Volume:

.. code-block:: bash

   dvc push

Commit the pointer to git:

.. code-block:: bash

   git add data/dataset.csv.dvc .gitignore
   git commit -m "track dataset v1 with DVC"
   git push

Pull data in another environment:

.. code-block:: bash

   git clone <your-repo>
   pip install dvc-databricks
   export DATABRICKS_CONFIG_PROFILE=<your-profile-name>
   dvc pull

How it works
------------

.. code-block:: text

   Your git repo                   Databricks Volume (S3 / ADLS)
   ──────────────────              ───────────────────────────────────
   data/dataset.csv.dvc  ──────►  /Volumes/catalog/schema/vol/
   .dvc/config                     └── files/md5/
                                       ├── ab/cdef1234...   ← actual data
                                       └── 9f/123abc...     ← actual data

``dvc add`` hashes the file and stores it in the local DVC cache (``.dvc/cache``).
A ``.dvc`` pointer file containing the MD5 hash is created next to your data file.

``dvc push`` uploads from the local cache to the Volume using the Databricks Files
API (``WorkspaceClient.files.upload``).

``dvc pull`` downloads from the Volume into the local cache, then restores the file
to its original path.

Only ``.dvc`` pointer files are ever committed to git — the data stays on the Volume.
