Installation
============

Requirements
------------

- Python >= 3.10
- `DVC <https://dvc.org/doc/install>`_ >= 3.0
- `Databricks CLI <https://docs.databricks.com/en/dev-tools/cli/install.html>`_ configured with a profile in ``~/.databrickscfg``
- Access to a Databricks Unity Catalog Volume

Install from PyPI
-----------------

.. code-block:: bash

   pip install dvc-databricks

Once installed, the ``dbvol://`` remote protocol is automatically available to DVC
in every process — no imports or additional configuration needed.

This works because the wheel installs a ``.pth`` file into ``site-packages`` that
runs ``import dvc_databricks`` at Python startup, registering the protocol before
any DVC command is executed.

Development installation
------------------------

.. code-block:: bash

   git clone https://github.com/ogreyesp/dvc-databricks
   cd dvc-databricks
   pip install -e ".[dev]"
