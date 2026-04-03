"""
layout_manager.py - Helper utilities for the Builder Mode layout UI.
Provides a tree-view panel so users can visually navigate and select nodes.
"""
from typing import Dict, Optional

import streamlit as st

from utils import state_manager as sm
from modules.component_registry import COMPONENT_META


def _node_label(node: Dict) -> str:
    """Build a human-readable label for a node."""
    comp_type = node.get("type", "unknown")
    meta = COMPONENT_META.get(comp_type, {})
    icon = meta.get("icon", "🧩")
    label_prop = node.get("props", {}).get("label") or node.get("props", {}).get("text", "")
    name_part = f" — {label_prop}" if label_prop else ""
    return f"{icon} {comp_type}{name_part}  `{node.get('id', '')}`"


def render_tree_panel(tree: Dict, depth: int = 0) -> None:
    """
    Recursively render the UI tree as an indented list of buttons.
    Clicking a node button selects it for editing.
    """
    indent = "  " * depth
    label = _node_label(tree)
    node_id = tree.get("id", "")
    selected = sm.get_selected_node_id()

    button_label = f"{indent}{'▶ ' if selected == node_id else ''}{label}"
    if st.button(button_label, key=f"tree_btn_{node_id}", use_container_width=True):
        sm.set_selected_node_id(node_id)
        st.rerun()

    for child in tree.get("children", []):
        render_tree_panel(child, depth + 1)
