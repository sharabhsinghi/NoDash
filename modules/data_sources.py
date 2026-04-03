"""
data_sources.py - Data source management for StreamCanvas.
Handles CSV / Excel uploads, preview, and session-state persistence.
File bytes are stored in session state keyed by filename.
"""
import io
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from utils import state_manager as sm


# ─── Load helpers ────────────────────────────────────────────────────────────

def load_dataframe(source_name: str) -> Optional[pd.DataFrame]:
    """Load a DataFrame from the stored bytes for the given source name."""
    data_sources: Dict = sm.get("data_sources", {})
    source = data_sources.get(source_name)
    if source is None:
        return None
    file_bytes: bytes = source.get("bytes", b"")
    file_type: str = source.get("type", "csv")
    try:
        buf = io.BytesIO(file_bytes)
        if file_type == "csv":
            return pd.read_csv(buf)
        if file_type in ("xlsx", "xls", "excel"):
            return pd.read_excel(buf)
    except Exception as exc:
        st.error(f"Error loading '{source_name}': {exc}")
    return None


def get_source_names() -> list:
    """Return a sorted list of registered data-source names."""
    return sorted(sm.get("data_sources", {}).keys())


# ─── Streamlit UI ─────────────────────────────────────────────────────────────

def render_data_sources_page() -> None:
    """Render the Data Sources management page."""
    st.header("📂 Data Sources")

    # ── Upload new source ──────────────────────────────────────────────────
    st.subheader("Upload a new data source")
    uploaded = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        key="ds_file_uploader",
    )

    if uploaded is not None:
        file_bytes = uploaded.read()
        ext = uploaded.name.rsplit(".", 1)[-1].lower()
        file_type = "csv" if ext == "csv" else "excel"

        source_name = st.text_input(
            "Source name (leave blank to use filename)",
            value=uploaded.name,
            key="ds_source_name_input",
        )
        if st.button("Add Source", key="ds_add_source_btn"):
            name = source_name.strip() or uploaded.name
            data_sources = sm.get("data_sources", {})
            data_sources[name] = {
                "name": name,
                "filename": uploaded.name,
                "type": file_type,
                "bytes": file_bytes,
            }
            sm.set_value("data_sources", data_sources)
            st.success(f"Data source '{name}' added successfully.")
            st.rerun()

    st.divider()

    # ── List existing sources ──────────────────────────────────────────────
    data_sources: Dict = sm.get("data_sources", {})
    if not data_sources:
        st.info("No data sources added yet. Upload a file above.")
        return

    st.subheader("Registered Data Sources")
    for name, source in data_sources.items():
        with st.expander(f"🗃️ {name}  ({source['type'].upper()})", expanded=False):
            df = load_dataframe(name)
            if df is not None:
                col1, col2, col3 = st.columns(3)
                col1.metric("Rows", df.shape[0])
                col2.metric("Columns", df.shape[1])
                col3.metric("Type", source["type"].upper())

                st.write("**Schema**")
                schema_df = pd.DataFrame(
                    {"Column": df.columns, "DType": df.dtypes.astype(str).values}
                )
                st.dataframe(schema_df, use_container_width=True, hide_index=True)

                st.write("**Preview (first 5 rows)**")
                st.dataframe(df.head(), use_container_width=True)

            if st.button(f"Remove '{name}'", key=f"ds_remove_{name}"):
                del data_sources[name]
                sm.set_value("data_sources", data_sources)
                st.rerun()
