"""
dataset_builder.py - Visual dataset transformation builder.
Allows renaming, calculated columns, filters, groupby, and pivot tables.
Dataset configs are stored in session state and resolved at render time.
"""
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from modules.data_sources import get_source_names, load_dataframe
from utils import state_manager as sm
from utils.transformations import execute_pipeline


# ─── Execution engine ─────────────────────────────────────────────────────────

def execute_dataset(dataset_config: Dict) -> Optional[pd.DataFrame]:
    """
    Execute a dataset config against the registered data sources.
    dataset_config: {
        "source": "source_name",
        "transformations": [{"type": "...", "params": {...}}, ...]
    }
    Returns a transformed DataFrame or None on error.
    """
    source_name = dataset_config.get("source", "")
    df = load_dataframe(source_name)
    if df is None:
        return None
    steps = dataset_config.get("transformations", [])
    try:
        df = execute_pipeline(df, steps)
    except Exception as exc:
        st.error(f"Transformation error in dataset '{dataset_config.get('name', '')}': {exc}")
        return None
    return df


def get_dataset_names() -> List[str]:
    """Return sorted list of configured dataset names."""
    return sorted(sm.get("datasets", {}).keys())


def get_dataset_df(name: str) -> Optional[pd.DataFrame]:
    """Return the executed DataFrame for a named dataset."""
    datasets: Dict = sm.get("datasets", {})
    config = datasets.get(name)
    if config is None:
        return None
    return execute_dataset(config)


# ─── Streamlit UI ─────────────────────────────────────────────────────────────

def _render_transformation_editor(steps: List[Dict]) -> List[Dict]:
    """Render an editor for a list of transformation steps. Returns updated steps."""
    step_types = ["rename", "calculated_column", "filter", "groupby", "pivot"]

    if st.button("➕ Add Transformation Step", key="ds_add_step"):
        steps.append({"type": "filter", "params": {"query": ""}})

    to_delete = []
    for idx, step in enumerate(steps):
        with st.expander(f"Step {idx + 1}: {step['type']}", expanded=True):
            step_type = st.selectbox(
                "Type",
                step_types,
                index=step_types.index(step["type"]) if step["type"] in step_types else 0,
                key=f"step_type_{idx}",
            )
            step["type"] = step_type
            params = step.get("params", {})

            if step_type == "rename":
                st.caption("Enter old→new column mappings, one per line: `old_name=new_name`")
                raw = params.get("_raw", "")
                raw = st.text_area("Mappings", value=raw, key=f"rename_raw_{idx}")
                mapping = {}
                for line in raw.splitlines():
                    if "=" in line:
                        k, _, v = line.partition("=")
                        mapping[k.strip()] = v.strip()
                step["params"] = {"mapping": mapping, "_raw": raw}

            elif step_type == "calculated_column":
                col_name = st.text_input("New column name", value=params.get("name", ""), key=f"calc_name_{idx}")
                expr = st.text_input("Expression (pandas eval)", value=params.get("expression", ""), key=f"calc_expr_{idx}")
                step["params"] = {"name": col_name, "expression": expr}

            elif step_type == "filter":
                query = st.text_input("Query (pandas query syntax)", value=params.get("query", ""), key=f"filter_q_{idx}")
                step["params"] = {"query": query}

            elif step_type == "groupby":
                cols_raw = st.text_input(
                    "Group-by columns (comma separated)",
                    value=", ".join(params.get("columns", [])),
                    key=f"gb_cols_{idx}",
                )
                agg_raw = params.get("_agg_raw", "")
                agg_raw = st.text_area(
                    "Aggregations (one per line: column=func)",
                    value=agg_raw,
                    key=f"gb_agg_{idx}",
                )
                agg = {}
                for line in agg_raw.splitlines():
                    if "=" in line:
                        k, _, v = line.partition("=")
                        agg[k.strip()] = v.strip()
                step["params"] = {
                    "columns": [c.strip() for c in cols_raw.split(",") if c.strip()],
                    "aggregations": agg,
                    "_agg_raw": agg_raw,
                }

            elif step_type == "pivot":
                step["params"] = {
                    "index": st.text_input("Index column", value=params.get("index", ""), key=f"piv_idx_{idx}"),
                    "columns": st.text_input("Columns field", value=params.get("columns", ""), key=f"piv_col_{idx}"),
                    "values": st.text_input("Values field", value=params.get("values", ""), key=f"piv_val_{idx}"),
                    "aggfunc": st.selectbox("Aggregation", ["sum", "mean", "count", "min", "max"],
                                            index=["sum", "mean", "count", "min", "max"].index(
                                                params.get("aggfunc", "sum")),
                                            key=f"piv_agg_{idx}"),
                }

            if st.button(f"🗑️ Remove Step {idx + 1}", key=f"remove_step_{idx}"):
                to_delete.append(idx)

    for idx in reversed(to_delete):
        steps.pop(idx)

    return steps


def render_dataset_builder_page() -> None:
    """Render the Dataset Builder page."""
    st.header("🔧 Dataset Builder")

    source_names = get_source_names()
    if not source_names:
        st.warning("No data sources available. Please add a data source first.")
        return

    datasets: Dict = sm.get("datasets", {})

    # ── Create new dataset ─────────────────────────────────────────────────
    st.subheader("Create / Edit Dataset")
    new_name = st.text_input("Dataset name", key="db_new_name")

    if new_name and new_name not in datasets:
        if st.button("Create Dataset", key="db_create"):
            datasets[new_name] = {
                "name": new_name,
                "source": source_names[0],
                "transformations": [],
            }
            sm.set_value("datasets", datasets)
            st.rerun()

    st.divider()

    # ── Edit existing datasets ─────────────────────────────────────────────
    if not datasets:
        st.info("No datasets yet. Enter a name above and click Create Dataset.")
        return

    selected_ds = st.selectbox("Select dataset to edit", list(datasets.keys()), key="db_selected")
    config = datasets[selected_ds]

    config["source"] = st.selectbox(
        "Source",
        source_names,
        index=source_names.index(config["source"]) if config["source"] in source_names else 0,
        key="db_source_select",
    )

    st.subheader("Transformation Pipeline")
    config["transformations"] = _render_transformation_editor(config.get("transformations", []))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Dataset", key="db_save"):
            datasets[selected_ds] = config
            sm.set_value("datasets", datasets)
            st.success(f"Dataset '{selected_ds}' saved.")

    with col2:
        if st.button("🗑️ Delete Dataset", key="db_delete"):
            del datasets[selected_ds]
            sm.set_value("datasets", datasets)
            st.rerun()

    # ── Preview ────────────────────────────────────────────────────────────
    st.subheader("Preview")
    if st.button("▶ Execute & Preview", key="db_preview"):
        df = execute_dataset(config)
        if df is not None:
            st.write(f"Shape: {df.shape}")
            st.dataframe(df.head(20), use_container_width=True)
