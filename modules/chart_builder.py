"""
chart_builder.py - Plotly chart configuration helper for StreamCanvas Builder Mode.
Provides a UI to configure a plotly_chart node's props interactively.
"""
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.dataset_builder import get_dataset_df, get_dataset_names


CHART_TYPES: List[str] = ["bar", "line", "scatter", "pie"]


def render_chart_builder(props: Dict) -> Dict:
    """
    Render an interactive chart-configuration UI.
    Returns the updated props dict.
    """
    dataset_names = get_dataset_names()

    if not dataset_names:
        st.warning("No datasets available. Create a dataset first.")
        return props

    dataset_name = st.selectbox(
        "Dataset",
        dataset_names,
        index=dataset_names.index(props.get("dataset", dataset_names[0]))
        if props.get("dataset") in dataset_names else 0,
        key="cb_dataset",
    )
    props["dataset"] = dataset_name

    # Load column names for the selected dataset
    df: Optional[pd.DataFrame] = get_dataset_df(dataset_name)
    columns: List[str] = list(df.columns) if df is not None else []
    col_options = [""] + columns

    chart_type = st.selectbox(
        "Chart type",
        CHART_TYPES,
        index=CHART_TYPES.index(props.get("chart_type", "bar"))
        if props.get("chart_type") in CHART_TYPES else 0,
        key="cb_chart_type",
    )
    props["chart_type"] = chart_type

    x_default = props.get("x", "")
    y_default = props.get("y", "")

    if columns:
        x_idx = col_options.index(x_default) if x_default in col_options else 0
        y_idx = col_options.index(y_default) if y_default in col_options else 0
        props["x"] = st.selectbox("X axis / Names", col_options, index=x_idx, key="cb_x")
        props["y"] = st.selectbox("Y axis / Values", col_options, index=y_idx, key="cb_y")
    else:
        props["x"] = st.text_input("X axis / Names column", value=x_default, key="cb_x_txt")
        props["y"] = st.text_input("Y axis / Values column", value=y_default, key="cb_y_txt")

    props["title"] = st.text_input("Chart title", value=props.get("title", ""), key="cb_title")
    props["use_container_width"] = st.checkbox(
        "Use container width", value=bool(props.get("use_container_width", True)), key="cb_ucw"
    )

    # Live preview
    if df is not None and st.button("🔍 Preview Chart", key="cb_preview"):
        _preview_chart(df, props)

    return props


def _preview_chart(df: pd.DataFrame, props: Dict) -> None:
    """Render a live chart preview inside the builder."""
    chart_type = props.get("chart_type", "bar")
    x_col = props.get("x") or None
    y_col = props.get("y") or None
    title = props.get("title", "")
    kw = {"title": title} if title else {}
    try:
        if chart_type == "bar":
            fig = px.bar(df, x=x_col, y=y_col, **kw)
        elif chart_type == "line":
            fig = px.line(df, x=x_col, y=y_col, **kw)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col, y=y_col, **kw)
        elif chart_type == "pie":
            fig = px.pie(df, names=x_col, values=y_col, **kw)
        else:
            fig = px.bar(df, x=x_col, y=y_col, **kw)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.error(f"Preview error: {exc}")
