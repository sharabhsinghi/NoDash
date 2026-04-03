"""
app.py - StreamCanvas main entry point.
Provides three top-level pages:
  • Builder   — integrated visual canvas, preview & save
  • Data Sources  — upload and manage raw data files
  • Dataset Builder — transform / filter data

Run with: streamlit run app.py
"""
import json

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
from modules.render_engine import render_dashboard, build_datasets
from modules.data_sources import render_data_sources_page
from modules.dataset_builder import render_dataset_builder_page
from modules.persistence import save_dashboard, load_all_dashboards, load_dashboard, delete_dashboard
from modules.visual_builder import render_builder_canvas

# ─── Initialise session state ─────────────────────────────────────────────────
sm.init_state()
if "builder_preview_mode" not in st.session_state:
    st.session_state["builder_preview_mode"] = False


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

    Build mode  — full-width visual canvas + Preview button.
                  Component configuration happens in popup modal dialogs
                  (click ✏️ to edit, ➕ to add).
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
        # ── Build Mode — full-width canvas ────────────────────────────────────
        render_builder_canvas(tree, resolved_datasets)

        # Raw JSON editor (collapsible, for advanced users)
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
