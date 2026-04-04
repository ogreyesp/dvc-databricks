dvc-databricks
==============

A `DVC <https://dvc.org>`_ remote storage plugin that enables data versioning on
**Databricks Unity Catalog Volumes**.

Store large data files on Databricks Volumes (backed by S3 or ADLS), keep only
lightweight ``.dvc`` pointer files in your git repository, and use standard DVC
commands — no custom code required.

.. code-block:: bash

   dvc push   # uploads data to Databricks Volume via Databricks SDK
   dvc pull   # downloads data from Databricks Volume

.. toctree::
   :maxdepth: 2
   :caption: Contents

   installation
   usage
   cli
   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
