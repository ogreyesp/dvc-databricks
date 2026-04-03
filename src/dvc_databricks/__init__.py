"""
dvc-databricks — DVC remote plugin for Databricks Unity Catalog Volumes.

Registers the ``dbvol`` protocol into ``dvc_objects.fs.known_implementations``
so that DVC can resolve ``dbvol://`` remotes in any process where this
package is installed.

This registration runs on import. The package uses a .pth file (installed
into site-packages) to ensure this module is imported at Python startup,
which makes ``dvc push`` / ``dvc pull`` work from the CLI without any
manual imports.
"""
from dvc_objects.fs import known_implementations

known_implementations["dbvol"] = {
    "class": "dvc_databricks.filesystem.DatabricksVolumesFileSystem",
}
