"""
state_manager.py - Manages Streamlit session state for StreamCanvas.
Centralises all session state initialisation and access patterns.
"""
import streamlit as st
from typing import Any, Dict, Optional


# ─── Default UI tree (empty root container) ───────────────────────────────────
DEFAULT_UI_TREE: Dict = {
    "id": "root",
    "type": "container",
    "props": {"label": "Root"},
    "children": [],
}


def init_state() -> None:
    """Initialise all required session-state keys with safe defaults."""
    defaults: Dict[str, Any] = {
        # Raw uploaded file objects (name -> bytes)
        "data_sources": {},
        # Transformed dataset configurations  {name -> dataset_config_dict}
        "datasets": {},
        # The live UI tree JSON
        "ui_tree": DEFAULT_UI_TREE.copy(),
        # ID of the node currently selected in Builder Mode
        "selected_node_id": None,
        # List of persisted dashboard dicts {id, name, config}
        "dashboards": [],
        # Current application mode: "builder" | "renderer" | "data"
        "app_mode": "builder",
        # Clipboard for copy-paste of nodes
        "clipboard_node": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ─── Convenience accessors ────────────────────────────────────────────────────

def get(key: str, default: Any = None) -> Any:
    """Safely retrieve a value from session state."""
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    """Set a value in session state."""
    st.session_state[key] = value


def get_ui_tree() -> Dict:
    """Return the current UI tree."""
    return st.session_state.get("ui_tree", DEFAULT_UI_TREE.copy())


def set_ui_tree(tree: Dict) -> None:
    """Replace the entire UI tree."""
    st.session_state["ui_tree"] = tree


def get_selected_node_id() -> Optional[str]:
    """Return the currently selected node ID."""
    return st.session_state.get("selected_node_id")


def set_selected_node_id(node_id: Optional[str]) -> None:
    """Set the selected node ID."""
    st.session_state["selected_node_id"] = node_id


# ─── Node helpers ─────────────────────────────────────────────────────────────

def find_node(tree: Dict, node_id: str) -> Optional[Dict]:
    """Recursively find a node by ID in the UI tree."""
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        result = find_node(child, node_id)
        if result is not None:
            return result
    return None


def find_parent(tree: Dict, node_id: str) -> Optional[Dict]:
    """Recursively find the parent of a node by child ID."""
    for child in tree.get("children", []):
        if child.get("id") == node_id:
            return tree
        result = find_parent(child, node_id)
        if result is not None:
            return result
    return None


def delete_node(tree: Dict, node_id: str) -> bool:
    """
    Remove a node from the tree by ID.
    Returns True if the node was found and deleted.
    """
    children = tree.get("children", [])
    for i, child in enumerate(children):
        if child.get("id") == node_id:
            children.pop(i)
            return True
        if delete_node(child, node_id):
            return True
    return False


def add_child_node(tree: Dict, parent_id: str, new_node: Dict) -> bool:
    """
    Add new_node as a child of the node with parent_id.
    Returns True if successful.
    """
    parent = find_node(tree, parent_id)
    if parent is None:
        return False
    if "children" not in parent:
        parent["children"] = []
    parent["children"].append(new_node)
    return True


def update_node_props(tree: Dict, node_id: str, new_props: Dict) -> bool:
    """
    Merge new_props into the props of the target node.
    Returns True if the node was found and updated.
    """
    node = find_node(tree, node_id)
    if node is None:
        return False
    node["props"].update(new_props)
    return True
