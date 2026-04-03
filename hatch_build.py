"""
Hatchling build hook that installs dvc_databricks_startup.pth into site-packages.

The .pth file contains a single ``import dvc_databricks`` statement. Python
executes all .pth files in site-packages at interpreter startup, which
registers the ``dbvol`` protocol into ``dvc_objects.known_implementations``
before DVC runs any command — making ``dvc push`` / ``dvc pull`` work from
the CLI without any manual imports.
"""
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        build_data["shared_data"] = {
            "dvc_databricks_startup.pth": "src/dvc_databricks_startup.pth",
        }
