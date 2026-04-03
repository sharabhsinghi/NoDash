"""
visual_builder.py - Visual WYSIWYG canvas for StreamCanvas Builder Mode.

Renders the UI tree with builder chrome (select/delete/add buttons) around
every component so users can see their layout as they build it.
"""
from typing import Dict

import streamlit as st

from modules.component_registry import COMPONENT_META, get_component_types
from modules.render_engine import render_node
from utils import state_manager as sm
from utils.id_generator import generate_id


# ─── Helpers ──────────────────────────────────────────────────────────────────

def build_new_node(comp_type: str) -> dict:
    """Create a new node dict with schema defaults for the given component type."""
    meta = COMPONENT_META.get(comp_type, {})
    props = {}
    for prop in meta.get("props_schema", []):
        props[prop["name"]] = prop.get("default", "")
    return {
        "id": generate_id(comp_type),
        "type": comp_type,
        "props": props,
        "children": [],
    }


def reassign_ids(node: dict) -> None:
    """Recursively assign fresh IDs to a node and all its descendants."""
    node["id"] = generate_id(node.get("type", "node"))
    for child in node.get("children", []):
        reassign_ids(child)


def _node_display_label(node: Dict) -> str:
    """Short human-readable label for a node (shown in the chrome header)."""
    comp_type = node.get("type", "unknown")
    meta = COMPONENT_META.get(comp_type, {})
    icon = meta.get("icon", "🧩")
    props = node.get("props", {})
    name = props.get("label") or props.get("text") or props.get("content", "")
    if name:
        name = str(name)
        if len(name) > 35:
            name = name[:35] + "…"
    name_str = f": *{name}*" if name else ""
    return f"{icon} `{comp_type}`{name_str}"


# ─── Inline add-component widget ──────────────────────────────────────────────

def render_add_widget(parent_id: str, button_label: str = "➕ Add Component") -> None:
    """
    Render a small add-component widget.

    • When idle: shows a single button labelled *button_label*.
    • When active (this parent is being targeted): shows an inline
      type-picker with Confirm / Cancel buttons.
    """
    is_adding = st.session_state.get("adding_to_node_id") == parent_id

    if is_adding:
        with st.container(border=True):
            col_type, col_ok, col_cancel = st.columns([3, 1, 1])
            with col_type:
                comp_type = st.selectbox(
                    "Component type",
                    get_component_types(),
                    key=f"add_type_select_{parent_id}",
                    label_visibility="collapsed",
                )
            with col_ok:
                if st.button("✅ Add", key=f"confirm_add_{parent_id}"):
                    new_node = build_new_node(comp_type)
                    tree = sm.get_ui_tree()
                    sm.add_child_node(tree, parent_id, new_node)
                    sm.set_ui_tree(tree)
                    sm.set_selected_node_id(new_node["id"])
                    st.session_state["adding_to_node_id"] = None
                    st.rerun()
            with col_cancel:
                if st.button("✖ Cancel", key=f"cancel_add_{parent_id}"):
                    st.session_state["adding_to_node_id"] = None
                    st.rerun()
    else:
        if st.button(
            button_label,
            key=f"add_btn_{parent_id}",
            use_container_width=True,
        ):
            st.session_state["adding_to_node_id"] = parent_id
            st.rerun()


# ─── Canvas node renderer ──────────────────────────────────────────────────────

def render_canvas_node(node: Dict, datasets: Dict, depth: int = 0) -> None:
    """
    Recursively render a single node with builder chrome.

    Builder chrome consists of:
      • A header row: type label | ✏️ select-to-edit | 🗑️ delete
      • The component's visual representation (actual render for leaf nodes,
        bordered layout with child slots for container nodes)
      • For container nodes: an inline add-child widget at the bottom
    """
    node_id = node["id"]
    comp_type = node.get("type", "")
    meta = COMPONENT_META.get(comp_type, {})
    is_container = meta.get("can_have_children", False)
    is_selected = sm.get_selected_node_id() == node_id

    with st.container(border=is_selected):
        # ── Chrome header ─────────────────────────────────────────────────
        h1, h2, h3 = st.columns([5, 1, 1])
        with h1:
            lbl = _node_display_label(node)
            if is_selected:
                st.markdown(f"<small>🔷 **{lbl}** *(selected)*</small>", unsafe_allow_html=True)
            else:
                st.markdown(f"<small>{lbl}</small>", unsafe_allow_html=True)
        with h2:
            icon = "🔷" if is_selected else "✏️"
            if st.button(icon, key=f"sel_{node_id}", help="Select / deselect for editing"):
                sm.set_selected_node_id(None if is_selected else node_id)
                st.rerun()
        with h3:
            if st.button("🗑️", key=f"del_{node_id}", help="Delete component"):
                tree = sm.get_ui_tree()
                sm.delete_node(tree, node_id)
                sm.set_ui_tree(tree)
                if is_selected:
                    sm.set_selected_node_id(None)
                st.rerun()

        # ── Component body ────────────────────────────────────────────────
        if comp_type == "container":
            border = node.get("props", {}).get("border", False)
            with st.container(border=border):
                children = node.get("children", [])
                if not children:
                    st.caption("*Empty container — add a component below*")
                for child in children:
                    render_canvas_node(child, datasets, depth=depth + 1)
            render_add_widget(node_id, "➕ Add inside container")

        elif comp_type == "columns":
            ratios_raw = node.get("props", {}).get("ratios", "1,1")
            try:
                ratios = [float(r.strip()) for r in str(ratios_raw).split(",") if r.strip()]
            except ValueError:
                ratios = [1, 1]
                st.warning(f"Invalid column ratios '{ratios_raw}', using default [1, 1].")
            num_cols = len(ratios)
            children = node.get("children", [])

            cols_objs = st.columns(ratios)
            if not children:
                for i, col in enumerate(cols_objs):
                    with col:
                        st.caption(f"*Column {i + 1} (empty)*")
            else:
                for child in children:
                    col_idx = int(child.get("props", {}).get("column_index", 0))
                    col_idx = max(0, min(col_idx, num_cols - 1))
                    with cols_objs[col_idx]:
                        render_canvas_node(child, datasets, depth=depth + 1)

            render_add_widget(node_id, f"➕ Add to columns ({ratios_raw})")

        elif comp_type == "tabs":
            labels_raw = node.get("props", {}).get("tab_labels", "Tab 1,Tab 2")
            labels = [lbl.strip() for lbl in str(labels_raw).split(",") if lbl.strip()]
            if not labels:
                labels = ["Tab 1"]
            children = node.get("children", [])

            tabs_objs = st.tabs(labels)
            if not children:
                with tabs_objs[0]:
                    st.caption("*Empty tab — add a component below*")
            else:
                for child in children:
                    tab_idx = int(child.get("props", {}).get("tab_index", 0))
                    tab_idx = max(0, min(tab_idx, len(tabs_objs) - 1))
                    with tabs_objs[tab_idx]:
                        render_canvas_node(child, datasets, depth=depth + 1)

            render_add_widget(node_id, "➕ Add to tabs")

        elif is_container:
            # Generic container fallback
            children = node.get("children", [])
            if not children:
                st.caption("*Empty — add a component below*")
            for child in children:
                render_canvas_node(child, datasets, depth=depth + 1)
            render_add_widget(node_id, "➕ Add inside")

        else:
            # Leaf node: render the actual Streamlit component
            render_node(node, datasets)


# ─── Canvas entry point ────────────────────────────────────────────────────────

def render_builder_canvas(tree: Dict, datasets: Dict) -> None:
    """
    Render the full builder canvas.

    Iterates the root node's children and renders each with builder chrome.
    A top-level add button lets users append components at the root level.
    """
    children = tree.get("children", [])

    if not children:
        st.info("🎨 Your canvas is empty. Click the button below to add your first component!")
    else:
        for child in children:
            render_canvas_node(child, datasets, depth=0)

    st.divider()
    render_add_widget(tree["id"], "➕ Add Component")
