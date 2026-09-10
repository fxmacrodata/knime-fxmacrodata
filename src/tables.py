"""Lossless response retention alongside idiomatic KNIME scalar columns."""
from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd
from fxmacrodata_public import Result

WEBSITE = "https://fxmacrodata.com/?utm_source=knime&utm_medium=integration&utm_campaign=open_source_integrations&utm_content=app"
DOCUMENTATION = "https://fxmacrodata.com/documentation/reference?utm_source=knime&utm_medium=integration&utm_campaign=open_source_integrations&utm_content=docs"


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def records_frame(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, str]]:
    """Keep original field names and scalar types; encode nested values as JSON.

    Missing values remain missing. No units, dates, predictions or prices are
    inferred. Mixed/nested columns use JSON text to avoid lossy coercion; the
    response output retains the complete original API response separately.
    """
    names = list(dict.fromkeys(name for row in records for name in row))
    if not names:
        return pd.DataFrame({"_fxmd_empty": pd.Series([None] * len(records), dtype="boolean")}), {}
    columns = {}
    formats = {}
    for name in names:
        values = [row.get(name) for row in records]
        present = [value for value in values if value is not None]
        if not present or all(isinstance(value, str) for value in present):
            dtype, encoding = "string", "string"
        elif all(isinstance(value, bool) for value in present):
            dtype, encoding = "boolean", "boolean"
        elif all(type(value) is int and -(2**63) <= value < 2**63 for value in present):
            dtype, encoding = "Int64", "integer"
        elif all(type(value) in (int, float) and math.isfinite(value) and
                 (type(value) is float or abs(value) <= 2**53) for value in present):
            dtype, encoding = "Float64", "number"
        else:
            dtype, encoding = "string", "json"
            values = [None if value is None else json_text(value) for value in values]
        columns[name] = pd.Series(values, dtype=dtype)
        formats[name] = encoding
    return pd.DataFrame(columns), formats


def result_frames(result: Result) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = result.records()
    frame, encodings = records_frame(records)
    metadata = pd.DataFrame({
        "operation": pd.Series([result.operation], dtype="string"),
        "source_url": pd.Series([result.source_url], dtype="string"),
        "website_url": pd.Series([WEBSITE], dtype="string"),
        "documentation_url": pd.Series([DOCUMENTATION], dtype="string"),
        "record_count": pd.Series([len(frame)], dtype="Int64"),
        "status": pd.Series(["empty" if frame.empty else "available"], dtype="string"),
        "column_encodings_json": pd.Series([json_text(encodings)], dtype="string"),
        "response_json": pd.Series([json_text(result.payload)], dtype="string"),
    })
    return frame, metadata
