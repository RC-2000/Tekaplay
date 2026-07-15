"""Condition AST for game definitions.

Conditions are data, not code: a small JSON grammar over player state
(variables, flags, inventory) with all/any/not composition. Authors write
them in Creator Studio; the runtime evaluates them everywhere a branch,
option, or dialogue line can be gated.
"""
from __future__ import annotations

import operator
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

_OPS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}


class VarCondition(BaseModel):
    var: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte"] = "eq"
    value: int | float | str | bool


class FlagCondition(BaseModel):
    flag: str
    present: bool = True


class ItemCondition(BaseModel):
    item: str
    min_qty: int = Field(default=1, ge=1)


class AllCondition(BaseModel):
    all: list[Condition]


class AnyCondition(BaseModel):
    any: list[Condition]


class NotCondition(BaseModel):
    model_config = {"populate_by_name": True}

    not_: Condition = Field(alias="not")


Condition = Union[  # noqa: UP007  (Union kept for readable forward refs)
    VarCondition, FlagCondition, ItemCondition, AllCondition, AnyCondition, NotCondition
]

for _model in (AllCondition, AnyCondition, NotCondition):
    _model.model_rebuild()


def evaluate(condition: Condition | None, state: dict[str, Any]) -> bool:
    """True when the condition holds against player state. A None condition
    is unconditionally true (the common case)."""
    if condition is None:
        return True
    if isinstance(condition, VarCondition):
        current = state.get("variables", {}).get(condition.var)
        if current is None:
            return False
        try:
            return bool(_OPS[condition.op](current, condition.value))
        except TypeError:  # incomparable types authored by mistake → fail closed
            return False
    if isinstance(condition, FlagCondition):
        return (condition.flag in state.get("flags", [])) == condition.present
    if isinstance(condition, ItemCondition):
        return state.get("inventory", {}).get(condition.item, 0) >= condition.min_qty
    if isinstance(condition, AllCondition):
        return all(evaluate(c, state) for c in condition.all)
    if isinstance(condition, AnyCondition):
        return any(evaluate(c, state) for c in condition.any)
    if isinstance(condition, NotCondition):
        return not evaluate(condition.not_, state)
    return False  # pragma: no cover — unions are exhaustive
