"""Shared helpers for round-tripping pydantic models through CSV.

pandas infers numeric dtypes for ID-like string columns (transaction_id,
DUNS, NAICS code...) on read; this restores the schema-declared string type
before pydantic validation.
"""
from __future__ import annotations

from typing import Type

import pandas as pd
from pydantic import BaseModel


def string_field_names(model_cls: Type[BaseModel]) -> set[str]:
    return {
        name for name, field in model_cls.model_fields.items()
        if field.annotation is str or field.annotation == (str | None)
    }


def coerce_record(record: dict, string_fields: set[str]) -> dict:
    out = {}
    for k, v in record.items():
        if pd.isna(v) if not isinstance(v, (list, dict)) else False:
            v = None
        if v is not None and k in string_fields and isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(int(v)) if float(v).is_integer() else str(v)
        out[k] = v
    return out


def load_csv_as_models(path, model_cls: Type[BaseModel]) -> list[BaseModel]:
    df = pd.read_csv(path)
    string_fields = string_field_names(model_cls)
    rows = []
    for _, r in df.iterrows():
        record = coerce_record(r.to_dict(), string_fields)
        rows.append(model_cls.model_validate(record))
    return rows
