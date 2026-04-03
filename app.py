"""
app.py - StreamCanvas main entry point.
Provides three top-level pages:
  • Builder   — integrated visual canvas, property editor, preview & save
  • Data Sources  — upload and manage raw data files
  • Dataset Builder — transform / filter data

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
from utils.id_generator import generate_id
from modules.component_registry import COMPONENT_META, get_component_types
from modules.render_engine import render_dashboard, build_datasets
from modules.data_sources import render_data_sources_page
from modules.dataset_builder import render_dataset_builder_page, get_dataset_names
from modules.chart_builder import render_chart_builder
from modules.persistence import save_dashboard, load_all_dashboards, load_dashboard, delete_dashboard
from modules.visual_builder import render_builder_canvas, build_new_node, reassign_ids

# ─── Initialise session state ─────────────────────────────────────────────────
sm.init_state()
if "builder_preview_mode" not in st.session_state:
    st.session_state["builder_preview_mode"] = False
if "adding_to_node_id" not in st.session_state:
    st.session_state["adding_to_node_id"] = None


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
                "📂 Data Sources",
                "🔧 Dataset Builder",
            ],
            key="nav_page",
        )

        st.divider()
        st.caption("StreamCanvas v1.0.0")
    return page


# ─────────────────────────────────────────────────────────────────────────────
# Property editor helpers (used in the right panel of Builder Mode)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Inline save widget (used in preview mode)
# ─────────────────────────────────────────────────────────────────────────────

def _render_inline_save() -> None:
    """Compact save panel shown at the bottom of the preview screen."""
    st.divider()
    with st.container(border=True):
        st.caption("💾 **Save Dashboard**")
        col_name, col_save, col_export = st.columns([3, 1, 1])
        with col_name:
            dash_name = st.text_input(
                "Dashboard name",
                key="inline_save_name",
                label_visibility="collapsed",
                placeholder="Dashboard name…",
            )
        with col_save:
            if st.button("💾 Save", key="inline_save_btn", use_container_width=True, type="primary"):
                if not dash_name.strip():
                    st.warning("Enter a dashboard name.")
                else:
                    config = {
                        "ui_tree": sm.get_ui_tree(),
                        "datasets": sm.get("datasets", {}),
                    }
                    dash_id = save_dashboard(dash_name.strip(), config)
                    if dash_id:
                        st.success(f"Saved as **{dash_name}** (`{dash_id[:8]}…`)")
        with col_export:
            config_export = {
                "ui_tree": sm.get_ui_tree(),
                "datasets": sm.get("datasets", {}),
            }
            st.download_button(
                label="⬇️ Export",
                data=json.dumps(config_export, indent=2),
                file_name="dashboard_export.json",
                mime="application/json",
                key="inline_export_btn",
                use_container_width=True,
            )

        # Saved dashboards quick-load
        with st.expander("📂 Saved Dashboards", expanded=False):
            dashboards = load_all_dashboards()
            if not dashboards:
                st.info("No saved dashboards yet.")
            for dash in dashboards:
                dc1, dc2, dc3, dc4 = st.columns([3, 2, 1, 1])
                dc1.write(f"**{dash['name']}**")
                dc2.caption(dash["created_at"][:19].replace("T", " "))
                if dc3.button("Load", key=f"inline_load_{dash['id']}"):
                    config = load_dashboard(dash["id"])
                    if config:
                        sm.set_ui_tree(config.get("ui_tree", sm.DEFAULT_UI_TREE.copy()))
                        if "datasets" in config:
                            sm.set_value("datasets", config["datasets"])
                        st.session_state["builder_preview_mode"] = False
                        st.rerun()
                if dc4.button("Del", key=f"inline_del_{dash['id']}"):
                    delete_dashboard(dash["id"])
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Builder Mode
# ─────────────────────────────────────────────────────────────────────────────

def render_builder_page() -> None:
    """
    Render the integrated Builder page.

    Build mode  — visual canvas (left) + property editor (right) + Preview button.
    Preview mode — full rendered dashboard + Save/Export controls + Back button.
    """
    tree = sm.get_ui_tree()
    is_preview = st.session_state.get("builder_preview_mode", False)

    # Resolve datasets once per render pass
    resolved_datasets = build_datasets(sm.get("datasets", {}))

    if is_preview:
        # ── Preview Mode ─────────────────────────────────────────────────────
        st.subheader("👁️ Preview")
        st.caption("This is how your dashboard will look when rendered.")
        st.divider()

        render_dashboard({"ui_tree": tree, "datasets": sm.get("datasets", {})})

        _render_inline_save()

        st.divider()
        if st.button("← Back to Builder", key="preview_exit_btn"):
            st.session_state["builder_preview_mode"] = False
            st.rerun()

    else:
        # ── Build Mode ────────────────────────────────────────────────────────
        col_canvas, col_props = st.columns([3, 2])

        with col_canvas:
            st.subheader("🎨 Canvas")
            render_builder_canvas(tree, resolved_datasets)

        with col_props:
            selected_id = sm.get_selected_node_id()
            if selected_id is None:
                st.subheader("⚙️ Properties")
                st.info("Click ✏️ on a component in the canvas to edit its properties here.")

                # Raw JSON editor when nothing is selected
                with st.expander("🔍 Raw JSON", expanded=False):
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
            else:
                node = sm.find_node(tree, selected_id)
                if node is None:
                    st.warning(f"Node '{selected_id}' not found in tree.")
                    sm.set_selected_node_id(None)
                else:
                    st.subheader("⚙️ Properties")
                    st.markdown(
                        f"Editing **`{node['type']}`** — <small>`{selected_id}`</small>",
                        unsafe_allow_html=True,
                    )
                    st.divider()

                    _render_prop_editor(node)

                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾 Apply", key="prop_save", type="primary", use_container_width=True):
                            sm.set_ui_tree(tree)
                            st.success("Properties applied.")
                            st.rerun()
                    with c2:
                        if st.button("📋 Duplicate", key="prop_duplicate", use_container_width=True):
                            parent = sm.find_parent(tree, selected_id)
                            if parent is not None:
                                dup = copy.deepcopy(node)
                                dup["id"] = generate_id(node["type"])
                                reassign_ids(dup)
                                parent.setdefault("children", []).append(dup)
                                sm.set_ui_tree(tree)
                                st.rerun()
                    with c3:
                        if st.button("🗑️ Delete", key="prop_delete", use_container_width=True):
                            if selected_id == "root":
                                st.error("Cannot delete the root node.")
                            else:
                                sm.delete_node(tree, selected_id)
                                sm.set_selected_node_id(None)
                                sm.set_ui_tree(tree)
                                st.rerun()

        # ── Bottom bar: Preview button ─────────────────────────────────────
        st.divider()
        _, mid, _ = st.columns([2, 2, 2])
        with mid:
            if st.button(
                "👁️ Preview Dashboard",
                key="preview_btn",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["builder_preview_mode"] = True
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    page = render_sidebar()

    if page == "🏗️ Builder":
        st.header("🏗️ Builder Mode")
        st.caption("Design your dashboard visually. Click ✏️ to edit, 🗑️ to delete, ➕ to add.")
        st.divider()
        render_builder_page()

    elif page == "📂 Data Sources":
        render_data_sources_page()

    elif page == "🔧 Dataset Builder":
        render_dataset_builder_page()


if __name__ == "__main__":
    main()
