"""
render_engine.py - Recursive rendering engine for StreamCanvas.
Reads the JSON UI tree and renders each node deterministically.
The renderer is stateless: it only reads JSON + resolved datasets.
"""
from typing import Dict, Optional

import streamlit as st

from modules.component_registry import get_renderer
from modules.dataset_builder import execute_dataset


# ─── Dataset resolution ───────────────────────────────────────────────────────

def build_datasets(datasets_config: Dict) -> Dict:
    """
    Pre-execute all dataset configs and return a map of {name -> DataFrame}.
    This is called once per render pass for efficiency.
    """
    resolved = {}
    for name, config in datasets_config.items():
        df = execute_dataset(config)
        if df is not None:
            resolved[name] = df
    return resolved


# ─── Recursive node renderer ──────────────────────────────────────────────────

def render_node(node: Dict, datasets: Dict) -> None:
    """
    Recursively render a single UI tree node.
    - Looks up the component renderer by type.
    - Delegates rendering (including children) to the renderer.
    """
    if not isinstance(node, dict):
        return

    component_type = node.get("type", "")
    renderer = get_renderer(component_type)

    if renderer is None:
        st.warning(f"Unknown component type: '{component_type}' (id={node.get('id')})")
        return

    renderer(node, datasets)


# ─── Top-level dashboard renderer ────────────────────────────────────────────

def render_dashboard(config: Dict) -> None:
    """
    Entry point for Renderer Mode.
    config: full dashboard JSON  {ui_tree: {...}, datasets: {...}}
    Steps:
      1. Build datasets from config.
      2. Render UI tree recursively.
    """
    datasets_config = config.get("datasets", {})
    ui_tree = config.get("ui_tree", {})

    # Resolve all datasets up front for efficient repeated access
    resolved_datasets = build_datasets(datasets_config)

    if not ui_tree:
        st.info("This dashboard has no UI configured yet.")
        return

    render_node(ui_tree, resolved_datasets)
