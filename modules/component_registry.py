"""
component_registry.py - Registry and renderer for all StreamCanvas UI components.
Each component has a renderer function and a metadata entry describing its props.
New components can be added simply by registering a renderer and metadata.
"""
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.dataset_builder import get_dataset_df, get_dataset_names


# ─── Component metadata ───────────────────────────────────────────────────────
# Used by Builder Mode to provide a config UI for each component type.

COMPONENT_META: Dict[str, Dict] = {
    "container": {
        "label": "Container",
        "icon": "📦",
        "can_have_children": True,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Container"},
            {"name": "border", "type": "bool", "default": False},
        ],
    },
    "columns": {
        "label": "Columns Layout",
        "icon": "⬜",
        "can_have_children": True,
        "props_schema": [
            {"name": "ratios", "type": "text", "default": "1,1",
             "help": "Comma-separated column width ratios, e.g. 1,2,1"},
        ],
    },
    "tabs": {
        "label": "Tabs",
        "icon": "🗂️",
        "can_have_children": True,
        "props_schema": [
            {"name": "tab_labels", "type": "text", "default": "Tab 1,Tab 2",
             "help": "Comma-separated tab labels"},
        ],
    },
    "header": {
        "label": "Header",
        "icon": "🔠",
        "can_have_children": False,
        "props_schema": [
            {"name": "text", "type": "text", "default": "Header"},
            {"name": "level", "type": "int", "default": 1, "min": 1, "max": 6},
        ],
    },
    "markdown": {
        "label": "Markdown",
        "icon": "📝",
        "can_have_children": False,
        "props_schema": [
            {"name": "content", "type": "textarea", "default": "**Hello world**"},
        ],
    },
    "text": {
        "label": "Text",
        "icon": "💬",
        "can_have_children": False,
        "props_schema": [
            {"name": "content", "type": "text", "default": "Some text here"},
        ],
    },
    "button": {
        "label": "Button",
        "icon": "🔘",
        "can_have_children": False,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Click me"},
        ],
    },
    "selectbox": {
        "label": "Selectbox",
        "icon": "📋",
        "can_have_children": False,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Select an option"},
            {"name": "options", "type": "text", "default": "Option 1,Option 2,Option 3",
             "help": "Comma-separated options"},
        ],
    },
    "radio": {
        "label": "Radio",
        "icon": "🔵",
        "can_have_children": False,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Choose one"},
            {"name": "options", "type": "text", "default": "Option A,Option B",
             "help": "Comma-separated options"},
        ],
    },
    "checkbox": {
        "label": "Checkbox",
        "icon": "☑️",
        "can_have_children": False,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Check me"},
            {"name": "default_value", "type": "bool", "default": False},
        ],
    },
    "dataframe": {
        "label": "Dataframe",
        "icon": "📊",
        "can_have_children": False,
        "props_schema": [
            {"name": "dataset", "type": "dataset_select", "default": ""},
            {"name": "max_rows", "type": "int", "default": 100, "min": 1, "max": 10000},
            {"name": "use_container_width", "type": "bool", "default": True},
        ],
    },
    "plotly_chart": {
        "label": "Plotly Chart",
        "icon": "📈",
        "can_have_children": False,
        "props_schema": [
            {"name": "dataset", "type": "dataset_select", "default": ""},
            {"name": "chart_type", "type": "select", "default": "bar",
             "options": ["bar", "line", "scatter", "pie"]},
            {"name": "x", "type": "text", "default": ""},
            {"name": "y", "type": "text", "default": ""},
            {"name": "title", "type": "text", "default": ""},
            {"name": "use_container_width", "type": "bool", "default": True},
        ],
    },
    "metric": {
        "label": "Metric",
        "icon": "🔢",
        "can_have_children": False,
        "props_schema": [
            {"name": "label", "type": "text", "default": "Metric"},
            {"name": "value", "type": "text", "default": "42"},
            {"name": "delta", "type": "text", "default": ""},
        ],
    },
    "divider": {
        "label": "Divider",
        "icon": "➖",
        "can_have_children": False,
        "props_schema": [],
    },
}


# ─── Individual renderers ──────────────────────────────────────────────────────

def _render_container(node: Dict, datasets: Dict, context: Any = None) -> None:
    from modules.render_engine import render_node  # deferred import to avoid circular
    props = node.get("props", {})
    border = props.get("border", False)
    if border:
        with st.container(border=True):
            for child in node.get("children", []):
                render_node(child, datasets)
    else:
        with st.container():
            for child in node.get("children", []):
                render_node(child, datasets)


def _render_columns(node: Dict, datasets: Dict, context: Any = None) -> None:
    from modules.render_engine import render_node
    props = node.get("props", {})
    ratios_raw = props.get("ratios", "1,1")
    try:
        ratios = [float(r.strip()) for r in str(ratios_raw).split(",") if r.strip()]
    except ValueError:
        ratios = [1, 1]

    cols = st.columns(ratios)
    children = node.get("children", [])

    # Assign children to columns by their "column_index" prop
    for child in children:
        col_idx = int(child.get("props", {}).get("column_index", 0))
        col_idx = max(0, min(col_idx, len(cols) - 1))
        with cols[col_idx]:
            render_node(child, datasets)


def _render_tabs(node: Dict, datasets: Dict, context: Any = None) -> None:
    from modules.render_engine import render_node
    props = node.get("props", {})
    labels_raw = props.get("tab_labels", "Tab 1,Tab 2")
    labels = [lbl.strip() for lbl in str(labels_raw).split(",") if lbl.strip()]
    if not labels:
        labels = ["Tab 1"]

    tabs = st.tabs(labels)
    children = node.get("children", [])

    for child in children:
        tab_idx = int(child.get("props", {}).get("tab_index", 0))
        tab_idx = max(0, min(tab_idx, len(tabs) - 1))
        with tabs[tab_idx]:
            render_node(child, datasets)


def _render_header(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    text = props.get("text", "")
    level = int(props.get("level", 1))
    level = max(1, min(level, 6))
    prefix = "#" * level
    st.markdown(f"{prefix} {text}")


def _render_markdown(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    st.markdown(props.get("content", ""))


def _render_text(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    st.text(props.get("content", ""))


def _render_button(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    from utils.id_generator import generate_stable_key
    key = generate_stable_key(node["id"], "button")
    st.button(props.get("label", "Button"), key=key)


def _render_selectbox(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    from utils.id_generator import generate_stable_key
    options_raw = props.get("options", "")
    options = [o.strip() for o in str(options_raw).split(",") if o.strip()]
    key = generate_stable_key(node["id"], "selectbox")
    st.selectbox(props.get("label", "Select"), options or ["—"], key=key)


def _render_radio(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    from utils.id_generator import generate_stable_key
    options_raw = props.get("options", "")
    options = [o.strip() for o in str(options_raw).split(",") if o.strip()]
    key = generate_stable_key(node["id"], "radio")
    st.radio(props.get("label", "Choose"), options or ["—"], key=key)


def _render_checkbox(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    from utils.id_generator import generate_stable_key
    key = generate_stable_key(node["id"], "checkbox")
    st.checkbox(props.get("label", "Check"), value=bool(props.get("default_value", False)), key=key)


def _render_dataframe(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    dataset_name = props.get("dataset", "")
    max_rows = int(props.get("max_rows", 100))
    use_cw = bool(props.get("use_container_width", True))

    df: Optional[pd.DataFrame] = datasets.get(dataset_name)
    if df is None and dataset_name:
        df = get_dataset_df(dataset_name)

    if df is not None:
        st.dataframe(df.head(max_rows), use_container_width=use_cw)
    else:
        st.info(f"Dataset '{dataset_name}' not found or not loaded.")


def _render_plotly_chart(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    dataset_name = props.get("dataset", "")
    chart_type = props.get("chart_type", "bar")
    x_col = props.get("x", "")
    y_col = props.get("y", "")
    title = props.get("title", "")
    use_cw = bool(props.get("use_container_width", True))

    df: Optional[pd.DataFrame] = datasets.get(dataset_name)
    if df is None and dataset_name:
        df = get_dataset_df(dataset_name)

    if df is None:
        st.info(f"Dataset '{dataset_name}' not found.")
        return

    try:
        fig: Optional[go.Figure] = None
        kw: Dict[str, Any] = {"title": title} if title else {}

        if chart_type == "bar":
            fig = px.bar(df, x=x_col or None, y=y_col or None, **kw)
        elif chart_type == "line":
            fig = px.line(df, x=x_col or None, y=y_col or None, **kw)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x_col or None, y=y_col or None, **kw)
        elif chart_type == "pie":
            fig = px.pie(df, names=x_col or None, values=y_col or None, **kw)
        else:
            fig = px.bar(df, x=x_col or None, y=y_col or None, **kw)

        if fig:
            st.plotly_chart(fig, use_container_width=use_cw)
    except Exception as exc:
        st.error(f"Chart error: {exc}")


def _render_metric(node: Dict, datasets: Dict, context: Any = None) -> None:
    props = node.get("props", {})
    label = props.get("label", "Metric")
    value = props.get("value", "")
    delta = props.get("delta", "") or None
    st.metric(label=label, value=value, delta=delta)


def _render_divider(node: Dict, datasets: Dict, context: Any = None) -> None:
    st.divider()


# ─── Component registry ───────────────────────────────────────────────────────

_RENDERER_REGISTRY: Dict[str, Callable] = {
    "container": _render_container,
    "columns": _render_columns,
    "tabs": _render_tabs,
    "header": _render_header,
    "markdown": _render_markdown,
    "text": _render_text,
    "button": _render_button,
    "selectbox": _render_selectbox,
    "radio": _render_radio,
    "checkbox": _render_checkbox,
    "dataframe": _render_dataframe,
    "plotly_chart": _render_plotly_chart,
    "metric": _render_metric,
    "divider": _render_divider,
}


def get_renderer(component_type: str) -> Optional[Callable]:
    """Return the renderer function for a component type, or None if unknown."""
    return _RENDERER_REGISTRY.get(component_type)


def get_component_types() -> List[str]:
    """Return component types ordered by how frequently a user would add them.

    Layout containers come first, then data-display components, then content
    elements, and finally input widgets.
    """
    ordered = [
        # Layout / structural (added most often as scaffolding)
        "container",
        "columns",
        "tabs",
        # Data display
        "plotly_chart",
        "dataframe",
        "metric",
        # Content / text
        "header",
        "markdown",
        "text",
        "divider",
        # Input widgets
        "button",
        "selectbox",
        "radio",
        "checkbox",
    ]
    # Include any registered types not explicitly listed, sorted alphabetically
    extras = sorted(t for t in _RENDERER_REGISTRY if t not in ordered)
    return ordered + extras
