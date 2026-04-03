"""
visual_builder.py - Visual WYSIWYG canvas for StreamCanvas Builder Mode.

Renders the UI tree as close to the actual output as possible with minimal
builder chrome (a small label + ✏️ + 🗑️ row above each component).  Adding
and editing components is done entirely through popup modal dialogs, keeping
the canvas uncluttered.  Positioning (column / tab placement) uses sliders.
"""
import copy
from typing import Dict, Optional

import streamlit as st

from modules.component_registry import COMPONENT_META, get_component_types
from modules.render_engine import render_node
from modules.dataset_builder import get_dataset_names
from modules.chart_builder import render_chart_builder
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


# ─── Shared props form (used inside both Add and Edit dialogs) ─────────────────

def _render_props_form(node: dict, parent_node: Optional[Dict] = None,
                       key_prefix: str = "dlg_prop") -> None:
    """
    Render prop-editor widgets for *node* inside a dialog.

    • ``int`` fields use ``st.slider`` for compact range selection.
    • Positioning fields (column_index / tab_index) use sliders whose
      maximum is derived from the parent container's configuration.
    • All other field types mirror the main property editor behaviour.
    """
    comp_type = node.get("type", "")
    meta = COMPONENT_META.get(comp_type, {})
    props = node.get("props", {})
    dataset_names = get_dataset_names()

    for field in meta.get("props_schema", []):
        fname = field["name"]
        ftype = field.get("type", "text")
        fdefault = field.get("default", "")
        fhelp = field.get("help", "")
        current = props.get(fname, fdefault)
        key = f"{key_prefix}_{fname}"

        if ftype == "text":
            props[fname] = st.text_input(fname, value=str(current), key=key, help=fhelp)
        elif ftype == "textarea":
            props[fname] = st.text_area(fname, value=str(current), key=key, help=fhelp)
        elif ftype == "bool":
            props[fname] = st.checkbox(fname, value=bool(current), key=key, help=fhelp)
        elif ftype == "int":
            min_v = field.get("min", 0)
            max_v = field.get("max", 100)
            raw = current if current is not None else (fdefault if fdefault is not None else 0)
            props[fname] = st.slider(
                fname,
                min_value=min_v,
                max_value=max_v,
                value=int(raw),
                key=key,
                help=fhelp,
            )
        elif ftype == "select":
            options = field.get("options", [])
            idx = options.index(current) if current in options else 0
            props[fname] = st.selectbox(fname, options, index=idx, key=key, help=fhelp)
        elif ftype == "dataset_select":
            ds_options = [""] + dataset_names
            idx = ds_options.index(current) if current in ds_options else 0
            props[fname] = st.selectbox(fname, ds_options, index=idx, key=key, help=fhelp)

    # Special chart-builder panel
    if comp_type == "plotly_chart":
        st.write("---")
        st.write("**Chart Builder**")
        updated = render_chart_builder(props)
        props.update(updated)

    # Positioning sliders — only for non-container nodes placed inside a layout parent
    if comp_type not in ("container", "columns", "tabs", "root"):
        parent_type = parent_node.get("type", "") if parent_node else ""
        if parent_type == "columns":
            ratios_raw = parent_node.get("props", {}).get("ratios", "1,1")  # type: ignore[union-attr]
            try:
                num_cols = len([r for r in str(ratios_raw).split(",") if r.strip()])
            except Exception:
                num_cols = 2
            st.write("---")
            st.write("**Positioning**")
            props["column_index"] = st.slider(
                "Column index",
                min_value=0,
                max_value=max(0, num_cols - 1),
                value=int(props.get("column_index", 0)),
                key=f"{key_prefix}_column_index",
                help="Which column to place this component in",
            )
        elif parent_type == "tabs":
            labels_raw = parent_node.get("props", {}).get("tab_labels", "Tab 1,Tab 2")  # type: ignore[union-attr]
            try:
                num_tabs = len([l for l in str(labels_raw).split(",") if l.strip()])
            except Exception:
                num_tabs = 2
            st.write("---")
            st.write("**Positioning**")
            props["tab_index"] = st.slider(
                "Tab index",
                min_value=0,
                max_value=max(0, num_tabs - 1),
                value=int(props.get("tab_index", 0)),
                key=f"{key_prefix}_tab_index",
                help="Which tab to place this component in",
            )

    node["props"] = props


# ─── Modal dialogs ─────────────────────────────────────────────────────────────

@st.dialog("➕ Add Component", width="large")
def _show_add_dialog(parent_id: str) -> None:
    """
    Popup dialog for adding a new component.

    1. User picks a component type from a dropdown.
    2. The component's props form (with sliders for sizing / positioning)
       is shown inline.
    3. "Add to Dashboard" commits the new node into the tree and closes the
       dialog.
    """
    tree = sm.get_ui_tree()
    parent_node = sm.find_node(tree, parent_id)

    # ── Component type picker ──────────────────────────────────────────────
    comp_type = st.selectbox(
        "Select component type",
        get_component_types(),
        format_func=lambda t: (
            f"{COMPONENT_META.get(t, {}).get('icon', '🧩')}  "
            f"{COMPONENT_META.get(t, {}).get('label', t)}"
        ),
        key="dlg_add_comp_type",
    )

    # Rebuild working node when the type changes
    if st.session_state.get("dlg_add_node_type") != comp_type:
        st.session_state["dlg_add_node_type"] = comp_type
        st.session_state["dlg_add_node"] = build_new_node(comp_type)

    working_node = st.session_state["dlg_add_node"]

    # ── Props configuration ────────────────────────────────────────────────
    meta = COMPONENT_META.get(comp_type, {})
    has_props = bool(meta.get("props_schema")) or comp_type == "plotly_chart"
    if has_props:
        st.divider()
        st.write(
            f"**Configure "
            f"{COMPONENT_META.get(comp_type, {}).get('icon', '🧩')} "
            f"{COMPONENT_META.get(comp_type, {}).get('label', comp_type)}**"
        )
        _render_props_form(
            working_node,
            parent_node=parent_node,
            key_prefix=f"dlg_add_{working_node['id']}",
        )
    else:
        st.info("No configuration required for this component type.")

    st.divider()

    # ── Save / Cancel ──────────────────────────────────────────────────────
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button(
            "✅ Add to Dashboard",
            type="primary",
            use_container_width=True,
            key="dlg_add_save",
        ):
            sm.add_child_node(tree, parent_id, working_node)
            sm.set_ui_tree(tree)
            for k in ("dlg_add_node", "dlg_add_node_type"):
                st.session_state.pop(k, None)
            st.rerun()
    with col_cancel:
        if st.button("✖ Cancel", use_container_width=True, key="dlg_add_cancel"):
            for k in ("dlg_add_node", "dlg_add_node_type"):
                st.session_state.pop(k, None)
            st.rerun()


@st.dialog("✏️ Edit Component", width="large")
def _show_edit_dialog(node_id: str) -> None:
    """
    Popup dialog for editing an existing node's properties.

    Works on a deep copy so the original tree is only updated on explicit
    Save; Cancel discards all edits.
    """
    tree = sm.get_ui_tree()
    original_node = sm.find_node(tree, node_id)

    if original_node is None:
        st.error(f"Component '{node_id}' not found.")
        if st.button("Close", key="dlg_edit_not_found_close"):
            st.rerun()
        return

    parent_node = sm.find_parent(tree, node_id)
    comp_type = original_node.get("type", "")
    meta = COMPONENT_META.get(comp_type, {})

    st.write(
        f"**{meta.get('icon', '🧩')} {meta.get('label', comp_type)}** "
        f"— `{node_id}`"
    )
    st.divider()

    # Work on a deep copy so Cancel truly discards changes
    copy_key = f"dlg_edit_copy_{node_id}"
    if copy_key not in st.session_state:
        st.session_state[copy_key] = copy.deepcopy(original_node)
    working_node = st.session_state[copy_key]

    _render_props_form(
        working_node,
        parent_node=parent_node,
        key_prefix=f"dlg_edit_{node_id}",
    )

    st.divider()
    col_save, col_dup, col_del = st.columns(3)

    with col_save:
        if st.button(
            "💾 Save",
            type="primary",
            use_container_width=True,
            key=f"dlg_edit_save_{node_id}",
        ):
            actual = sm.find_node(tree, node_id)
            if actual is not None:
                actual["props"] = working_node["props"]
            sm.set_ui_tree(tree)
            st.session_state.pop(copy_key, None)
            st.rerun()

    with col_dup:
        if st.button(
            "📋 Duplicate",
            use_container_width=True,
            key=f"dlg_edit_dup_{node_id}",
        ):
            parent = sm.find_parent(tree, node_id)
            if parent is not None:
                dup = copy.deepcopy(original_node)
                dup["id"] = generate_id(original_node["type"])
                reassign_ids(dup)
                parent.setdefault("children", []).append(dup)
                sm.set_ui_tree(tree)
            st.session_state.pop(copy_key, None)
            st.rerun()

    with col_del:
        if st.button(
            "🗑️ Delete",
            use_container_width=True,
            key=f"dlg_edit_del_{node_id}",
        ):
            if node_id == "root":
                st.error("Cannot delete the root node.")
            else:
                sm.delete_node(tree, node_id)
                sm.set_selected_node_id(None)
                sm.set_ui_tree(tree)
                st.session_state.pop(copy_key, None)
                st.rerun()

    if st.button("✖ Cancel", use_container_width=True, key=f"dlg_edit_cancel_{node_id}"):
        st.session_state.pop(copy_key, None)
        st.rerun()


# ─── Add-component button ──────────────────────────────────────────────────────

def render_add_widget(parent_id: str, button_label: str = "➕ Add") -> None:
    """
    Show a compact Add button.  Clicking it opens the Add Component dialog.
    """
    if st.button(button_label, key=f"add_btn_{parent_id}", help="Add a component here"):
        _show_add_dialog(parent_id)


# ─── Canvas node renderer ──────────────────────────────────────────────────────

def render_canvas_node(node: Dict, datasets: Dict, depth: int = 0) -> None:
    """
    Render a single node with minimal builder chrome.

    The component is rendered exactly as it will appear in the final
    dashboard.  Above it sits a slim chrome row:
      label  |  ✏️ (opens Edit dialog)  |  🗑️ (deletes immediately)

    Container nodes additionally show a ➕ button at the bottom of their
    content area so children can be added inline.
    """
    node_id = node["id"]
    comp_type = node.get("type", "")
    meta = COMPONENT_META.get(comp_type, {})
    is_container = meta.get("can_have_children", False)

    # ── Slim chrome row ───────────────────────────────────────────────────
    lbl_col, edit_col, del_col = st.columns([6, 1, 1])
    with lbl_col:
        st.caption(_node_display_label(node))
    with edit_col:
        if st.button("✏️", key=f"edit_{node_id}", help="Edit component"):
            _show_edit_dialog(node_id)
    with del_col:
        if st.button("🗑️", key=f"del_{node_id}", help="Delete component"):
            tree = sm.get_ui_tree()
            sm.delete_node(tree, node_id)
            sm.set_ui_tree(tree)
            if sm.get_selected_node_id() == node_id:
                sm.set_selected_node_id(None)
            st.rerun()

    # ── Component body ────────────────────────────────────────────────────
    if comp_type == "container":
        border = node.get("props", {}).get("border", False)
        with st.container(border=border):
            children = node.get("children", [])
            if not children:
                st.caption("*Empty container — click ➕ to add a component*")
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

        render_add_widget(node_id, "➕ Add to columns")

    elif comp_type == "tabs":
        labels_raw = node.get("props", {}).get("tab_labels", "Tab 1,Tab 2")
        labels = [lbl.strip() for lbl in str(labels_raw).split(",") if lbl.strip()]
        if not labels:
            labels = ["Tab 1"]
        children = node.get("children", [])

        tabs_objs = st.tabs(labels)
        if not children:
            with tabs_objs[0]:
                st.caption("*Empty tab — click ➕ to add a component*")
        else:
            for child in children:
                tab_idx = int(child.get("props", {}).get("tab_index", 0))
                tab_idx = max(0, min(tab_idx, len(tabs_objs) - 1))
                with tabs_objs[tab_idx]:
                    render_canvas_node(child, datasets, depth=depth + 1)

        render_add_widget(node_id, "➕ Add to tabs")

    elif is_container:
        children = node.get("children", [])
        if not children:
            st.caption("*Empty — click ➕ to add a component*")
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

    Iterates the root node's children and renders each with minimal builder
    chrome.  A ➕ button at the bottom lets users add root-level components.
    """
    children = tree.get("children", [])

    if not children:
        st.info("🎨 Your canvas is empty. Click ➕ Add Component below to get started!")
    else:
        for child in children:
            render_canvas_node(child, datasets, depth=0)

    st.divider()
    render_add_widget(tree["id"], "➕ Add Component")
