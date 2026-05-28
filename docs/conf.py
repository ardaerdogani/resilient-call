"""Sphinx configuration for resilient-call documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "resilient-call"
copyright = "2026, Arda Erdoğan"
author = "Arda Erdoğan"
release = "1.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

autosummary_generate = True
autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
add_module_names = False

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
