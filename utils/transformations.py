"""
transformations.py - Dataset transformation pipeline.
Each transformation is a pure function: (DataFrame, params) -> DataFrame.
The execute_pipeline function applies a list of steps sequentially.
"""
import pandas as pd
from typing import Any, Dict, List


# ─── Individual transformations ───────────────────────────────────────────────

def apply_rename(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    Rename columns.
    params: {"mapping": {"old_name": "new_name", ...}}
    """
    mapping = params.get("mapping", {})
    if mapping:
        df = df.rename(columns=mapping)
    return df


def apply_calculated_column(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    Add a calculated column using a pandas eval expression.
    params: {"name": "new_col", "expression": "col_a + col_b"}
    """
    name = params.get("name", "").strip()
    expression = params.get("expression", "").strip()
    if name and expression:
        df[name] = df.eval(expression)
    return df


def apply_filter(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    Filter rows using a query string.
    params: {"query": "age > 30 and salary < 80000"}
    """
    query = params.get("query", "").strip()
    if query:
        df = df.query(query)
    return df


def apply_groupby(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    Group by columns and apply aggregations.
    params: {
        "columns": ["col1", "col2"],
        "aggregations": {"value_col": "sum", "other_col": "mean"}
    }
    """
    columns = params.get("columns", [])
    aggregations = params.get("aggregations", {})
    if columns and aggregations:
        df = df.groupby(columns, as_index=False).agg(aggregations)
    return df


def apply_pivot(df: pd.DataFrame, params: Dict) -> pd.DataFrame:
    """
    Create a pivot table.
    params: {
        "index": "row_col",
        "columns": "col_col",
        "values": "value_col",
        "aggfunc": "sum"
    }
    """
    index = params.get("index")
    columns = params.get("columns")
    values = params.get("values")
    aggfunc = params.get("aggfunc", "sum")
    if index and columns and values:
        df = df.pivot_table(
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc,
        )
        df = df.reset_index()
        df.columns = [str(c) for c in df.columns]
    return df


# ─── Transformation registry ──────────────────────────────────────────────────

_TRANSFORM_REGISTRY = {
    "rename": apply_rename,
    "calculated_column": apply_calculated_column,
    "filter": apply_filter,
    "groupby": apply_groupby,
    "pivot": apply_pivot,
}


def execute_pipeline(df: pd.DataFrame, steps: List[Dict]) -> pd.DataFrame:
    """
    Apply a sequence of transformation steps to a DataFrame.
    Each step: {"type": "rename", "params": {...}}
    """
    for step in steps:
        step_type = step.get("type")
        params = step.get("params", {})
        transform_fn = _TRANSFORM_REGISTRY.get(step_type)
        if transform_fn:
            df = transform_fn(df, params)
    return df
