"""
persistence.py - Dashboard persistence layer for StreamCanvas.
Saves and loads dashboards using SQLite (default) or PostgreSQL.
Table: dashboards(id UUID, name TEXT, config JSON, created_at TIMESTAMP)
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st

# SQLAlchemy is used for database portability (SQLite by default)
try:
    from sqlalchemy import create_engine, text
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

# ─── Database configuration ───────────────────────────────────────────────────

# Override with a PostgreSQL URL via the STREAMCANVAS_DB_URL environment variable
_DEFAULT_DB_URL = "sqlite:///streamcanvas.sqlite"
_DB_URL = os.environ.get("STREAMCANVAS_DB_URL", _DEFAULT_DB_URL)

_ENGINE = None


def _get_engine():
    """Lazily create and return the SQLAlchemy engine."""
    global _ENGINE
    if not SQLALCHEMY_AVAILABLE:
        return None
    if _ENGINE is None:
        _ENGINE = create_engine(_DB_URL, future=True)
        _init_schema(_ENGINE)
    return _ENGINE


def _init_schema(engine) -> None:
    """Create the dashboards table if it does not exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS dashboards (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        config TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))


# ─── CRUD helpers ─────────────────────────────────────────────────────────────

def save_dashboard(name: str, config: Dict) -> str:
    """
    Persist a dashboard.
    Returns the dashboard ID (new UUID each save).
    """
    engine = _get_engine()
    if engine is None:
        st.error("SQLAlchemy is not available. Cannot save dashboard.")
        return ""

    dash_id = str(uuid.uuid4())
    config_json = json.dumps(config)
    created_at = datetime.utcnow().isoformat()

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO dashboards (id, name, config, created_at) "
                "VALUES (:id, :name, :config, :created_at)"
            ),
            {"id": dash_id, "name": name, "config": config_json, "created_at": created_at},
        )
    return dash_id


def load_all_dashboards() -> List[Dict]:
    """Return a list of all saved dashboards (id, name, created_at)."""
    engine = _get_engine()
    if engine is None:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, created_at FROM dashboards ORDER BY created_at DESC")
        ).fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2]} for r in rows]


def load_dashboard(dash_id: str) -> Optional[Dict]:
    """Load a full dashboard config by ID."""
    engine = _get_engine()
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT config FROM dashboards WHERE id = :id"),
            {"id": dash_id},
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def delete_dashboard(dash_id: str) -> None:
    """Delete a dashboard by ID."""
    engine = _get_engine()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dashboards WHERE id = :id"), {"id": dash_id})


# ─── Streamlit UI ─────────────────────────────────────────────────────────────

def render_persistence_page() -> None:
    """Render the dashboard persistence management page."""
    from utils import state_manager as sm

    st.header("💾 Dashboard Persistence")

    # ── Save current dashboard ─────────────────────────────────────────────
    st.subheader("Save Current Dashboard")
    dash_name = st.text_input("Dashboard name", key="persist_name")

    if st.button("💾 Save Dashboard", key="persist_save"):
        if not dash_name.strip():
            st.warning("Please enter a dashboard name.")
        else:
            config = {
                "ui_tree": sm.get_ui_tree(),
                "datasets": sm.get("datasets", {}),
            }
            dash_id = save_dashboard(dash_name.strip(), config)
            if dash_id:
                st.success(f"Dashboard '{dash_name}' saved with ID `{dash_id}`.")

    st.divider()

    # ── Load / delete saved dashboards ────────────────────────────────────
    st.subheader("Saved Dashboards")
    dashboards = load_all_dashboards()

    if not dashboards:
        st.info("No saved dashboards found.")
        return

    for dash in dashboards:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.write(f"**{dash['name']}**")
        col2.caption(f"Saved: {dash['created_at'][:19]}")
        with col3:
            btn_col1, btn_col2 = st.columns(2)
            if btn_col1.button("Load", key=f"load_{dash['id']}"):
                config = load_dashboard(dash["id"])
                if config:
                    sm.set_ui_tree(config.get("ui_tree", sm.DEFAULT_UI_TREE.copy()))
                    if "datasets" in config:
                        sm.set_value("datasets", config["datasets"])
                    st.success(f"Dashboard '{dash['name']}' loaded.")
                    st.rerun()
            if btn_col2.button("Del", key=f"del_{dash['id']}"):
                delete_dashboard(dash["id"])
                st.rerun()

    st.divider()

    # ── Export JSON ────────────────────────────────────────────────────────
    st.subheader("Export / Import JSON")
    config_export = {
        "ui_tree": sm.get_ui_tree(),
        "datasets": sm.get("datasets", {}),
    }
    st.download_button(
        label="⬇️ Export current dashboard as JSON",
        data=json.dumps(config_export, indent=2),
        file_name="dashboard_export.json",
        mime="application/json",
        key="persist_export",
    )

    st.write("**Import dashboard from JSON**")
    import_file = st.file_uploader("Upload JSON", type=["json"], key="persist_import")
    if import_file and st.button("Import", key="persist_import_btn"):
        try:
            config_import = json.loads(import_file.read())
            sm.set_ui_tree(config_import.get("ui_tree", sm.DEFAULT_UI_TREE.copy()))
            if "datasets" in config_import:
                sm.set_value("datasets", config_import["datasets"])
            st.success("Dashboard imported successfully.")
            st.rerun()
        except Exception as exc:
            st.error(f"Import failed: {exc}")
