"""
app.py - StreamCanvas main entry point.
Provides two top-level modes:
  • Builder Mode  — graphical UI tree editor
  • Renderer Mode — pure JSON → Streamlit renderer
  • Data Sources  — upload and manage raw data
  • Dataset Builder — transform data
  • Persistence   — save / load dashboards

Run with: streamlit run app.py
"""
import json
import copy

import streamlit as st

# ─── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="StreamCanvas",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Local imports ────────────────────────────────────────────────────────────
from utils import state_manager as sm
from utils.id_generator import generate_id, generate_stable_key
from modules.component_registry import COMPONENT_META, get_component_types
from modules.layout_manager import render_tree_panel
from modules.render_engine import render_dashboard
from modules.data_sources import render_data_sources_page
from modules.dataset_builder import render_dataset_builder_page, get_dataset_names
from modules.chart_builder import render_chart_builder
from modules.persistence import render_persistence_page

# ─── Initialise session state ─────────────────────────────────────────────────
sm.init_state()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """Render sidebar navigation and return the selected page."""
    with st.sidebar:
        st.title("🎨 StreamCanvas")
        st.caption("No-code Streamlit UI Builder")
        st.divider()

        page = st.radio(
            "Navigation",
            [
                "🏗️ Builder",
                "▶️ Renderer",
                "📂 Data Sources",
                "🔧 Dataset Builder",
                "💾 Persistence",
            ],
            key="nav_page",
        )

        st.divider()
        st.caption("StreamCanvas v1.0.0")
    return page


# ─────────────────────────────────────────────────────────────────────────────
# Builder Mode
# ─────────────────────────────────────────────────────────────────────────────

def _build_new_node(comp_type: str) -> dict:
    """Create a new node dict with defaults for the given component type."""
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


def _render_prop_editor(node: dict) -> None:
    """Render dynamic prop editors for the selected node."""
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
        key = f"prop_{node['id']}_{fname}"

        if ftype == "text":
            props[fname] = st.text_input(fname, value=str(current), key=key, help=fhelp)
        elif ftype == "textarea":
            props[fname] = st.text_area(fname, value=str(current), key=key, help=fhelp)
        elif ftype == "bool":
            props[fname] = st.checkbox(fname, value=bool(current), key=key, help=fhelp)
        elif ftype == "int":
            min_v = field.get("min", 0)
            max_v = field.get("max", 1000)
            props[fname] = st.number_input(
                fname, value=int(current or fdefault), min_value=min_v, max_value=max_v, key=key, help=fhelp
            )
        elif ftype == "select":
            options = field.get("options", [])
            idx = options.index(current) if current in options else 0
            props[fname] = st.selectbox(fname, options, index=idx, key=key, help=fhelp)
        elif ftype == "dataset_select":
            ds_options = [""] + dataset_names
            idx = ds_options.index(current) if current in ds_options else 0
            props[fname] = st.selectbox(fname, ds_options, index=idx, key=key, help=fhelp)

    # Special chart builder integration
    if comp_type == "plotly_chart":
        st.write("---")
        st.write("**Chart Builder**")
        updated = render_chart_builder(props)
        props.update(updated)

    # Column/tab placement helpers
    if comp_type not in ("container", "columns", "tabs", "root"):
        st.write("---")
        st.write("**Placement (for layout parents)**")
        props["column_index"] = st.number_input(
            "Column index (for columns parent)",
            value=int(props.get("column_index", 0)),
            min_value=0,
            key=f"col_idx_{node['id']}",
        )
        props["tab_index"] = st.number_input(
            "Tab index (for tabs parent)",
            value=int(props.get("tab_index", 0)),
            min_value=0,
            key=f"tab_idx_{node['id']}",
        )

    node["props"] = props


def render_builder_page() -> None:
    """Render the full Builder Mode page."""
    tree = sm.get_ui_tree()
    selected_id = sm.get_selected_node_id()

    # ── Two-column layout: tree | editor ─────────────────────────────────
    col_tree, col_editor = st.columns([1, 2])

    # ── Left: Component Tree ──────────────────────────────────────────────
    with col_tree:
        st.subheader("🌳 Component Tree")
        render_tree_panel(tree)

        st.divider()
        st.subheader("➕ Add Component")

        comp_type = st.selectbox(
            "Component type",
            get_component_types(),
            key="builder_comp_type",
        )

        # Choose parent node
        parent_id_options = [tree["id"]] + _collect_container_ids(tree)
        parent_id = st.selectbox(
            "Add inside node",
            parent_id_options,
            key="builder_parent_id",
        )

        if st.button("Add Component", key="builder_add_btn"):
            new_node = _build_new_node(comp_type)
            if sm.add_child_node(tree, parent_id, new_node):
                sm.set_ui_tree(tree)
                sm.set_selected_node_id(new_node["id"])
                st.rerun()
            else:
                st.error(f"Could not find parent node '{parent_id}'.")

    # ── Right: Property Editor ────────────────────────────────────────────
    with col_editor:
        st.subheader("✏️ Property Editor")

        if selected_id is None:
            st.info("Select a node in the tree to edit its properties.")
        else:
            node = sm.find_node(tree, selected_id)
            if node is None:
                st.warning(f"Node '{selected_id}' not found in tree.")
            else:
                st.write(f"**Editing:** `{node['type']}` — `{selected_id}`")

                _render_prop_editor(node)

                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button("💾 Save", key="prop_save"):
                        sm.set_ui_tree(tree)
                        st.success("Properties saved.")
                        st.rerun()

                with col2:
                    if st.button("📋 Duplicate", key="prop_duplicate"):
                        parent = sm.find_parent(tree, selected_id)
                        if parent is not None:
                            dup = copy.deepcopy(node)
                            dup["id"] = generate_id(node["type"])
                            _reassign_ids(dup)
                            parent.setdefault("children", []).append(dup)
                            sm.set_ui_tree(tree)
                            st.rerun()

                with col3:
                    if st.button("🗑️ Delete", key="prop_delete"):
                        if selected_id == "root":
                            st.error("Cannot delete the root node.")
                        else:
                            sm.delete_node(tree, selected_id)
                            sm.set_selected_node_id(None)
                            sm.set_ui_tree(tree)
                            st.rerun()

    # ── JSON viewer / editor ──────────────────────────────────────────────
    st.divider()
    with st.expander("🔍 View / Edit Raw JSON", expanded=False):
        raw_json = st.text_area(
            "UI Tree JSON",
            value=json.dumps(tree, indent=2),
            height=300,
            key="raw_json_editor",
        )
        if st.button("Apply JSON", key="apply_raw_json"):
            try:
                new_tree = json.loads(raw_json)
                sm.set_ui_tree(new_tree)
                st.success("JSON applied.")
                st.rerun()
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")


def _collect_container_ids(tree: dict) -> list:
    """Return IDs of all container-capable nodes (for parent selection)."""
    result = []
    for child in tree.get("children", []):
        meta = COMPONENT_META.get(child.get("type", ""), {})
        if meta.get("can_have_children", False):
            result.append(child["id"])
            result.extend(_collect_container_ids(child))
    return result


def _reassign_ids(node: dict) -> None:
    """Recursively assign new IDs to a node and all descendants (for duplicate)."""
    node["id"] = generate_id(node.get("type", "node"))
    for child in node.get("children", []):
        _reassign_ids(child)


# ─────────────────────────────────────────────────────────────────────────────
# Renderer Mode
# ─────────────────────────────────────────────────────────────────────────────

def render_renderer_page() -> None:
    """Render the Renderer Mode page (pure JSON → UI)."""
    st.header("▶️ Dashboard Renderer")
    st.caption("Renders the current UI tree deterministically from JSON.")
    st.divider()

    config = {
        "ui_tree": sm.get_ui_tree(),
        "datasets": sm.get("datasets", {}),
    }
    render_dashboard(config)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    page = render_sidebar()

    if page == "🏗️ Builder":
        st.header("🏗️ Builder Mode")
        st.caption("Design your dashboard visually. Changes are stored as JSON.")
        st.divider()
        render_builder_page()

    elif page == "▶️ Renderer":
        render_renderer_page()

    elif page == "📂 Data Sources":
        render_data_sources_page()

    elif page == "🔧 Dataset Builder":
        render_dataset_builder_page()

    elif page == "💾 Persistence":
        render_persistence_page()


if __name__ == "__main__":
    main()
