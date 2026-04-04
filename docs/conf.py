# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Make the src layout visible to Sphinx autodoc
sys.path.insert(0, os.path.abspath("../src"))

# ---------------------------------------------------------------------------
# Project information
# ---------------------------------------------------------------------------

project = "dvc-databricks"
copyright = "2025, Óscar Reyes"
author = "Óscar Reyes"

# Read the version from pyproject.toml to avoid duplicating it
try:
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with _pyproject.open("rb") as _f:
        version = release = tomllib.load(_f)["project"]["version"]
except Exception:
    version = release = "unknown"

# ---------------------------------------------------------------------------
# General configuration
# ---------------------------------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",       # Pull docstrings from source code
    "sphinx.ext.napoleon",      # Support Google/NumPy-style docstrings
    "sphinx.ext.viewcode",      # Add [source] links to API reference
    "sphinx.ext.intersphinx",   # Link to external docs (Python, DVC, etc.)
    "sphinx_autodoc_typehints", # Render type annotations as readable text
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# ---------------------------------------------------------------------------
# Autodoc settings
# ---------------------------------------------------------------------------

autodoc_member_order = "bysource"
autodoc_typehints = "description"
always_document_param_types = True

# ---------------------------------------------------------------------------
# Napoleon settings (Google-style docstrings)
# ---------------------------------------------------------------------------

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_rtype = True

# ---------------------------------------------------------------------------
# Intersphinx — cross-reference external packages
# ---------------------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fsspec": ("https://filesystem-spec.readthedocs.io/en/latest/", None),
}

# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

html_theme = "furo"
html_static_path = ["_static"]
html_title = f"{project} {version}"
