from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .codec import RawNumber
from .errors import SaveToolError


def escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def parse_pointer(pointer: str) -> list[str]:
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise SaveToolError(f"JSON Pointer must be empty or start with '/': {pointer!r}")
    parts = pointer[1:].split("/")
    result: list[str] = []
    for part in parts:
        index = 0
        while index < len(part):
            if part[index] == "~":
                if index + 1 >= len(part) or part[index + 1] not in "01":
                    raise SaveToolError(f"invalid JSON Pointer escape in {pointer!r}")
                index += 2
            else:
                index += 1
        result.append(part.replace("~1", "/").replace("~0", "~"))
    return result


def _array_index(token: str, length: int, *, add: bool = False) -> int:
    if token == "-" and add:
        return length
    if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
        raise SaveToolError(f"invalid JSON array index: {token!r}")
    index = int(token)
    limit = length if add else length - 1
    if index < 0 or index > limit:
        raise SaveToolError(f"JSON array index {index} is out of range")
    return index


def resolve(document: Any, pointer: str) -> Any:
    value = document
    for token in parse_pointer(pointer):
        if isinstance(value, dict):
            if token not in value:
                raise SaveToolError(f"JSON Pointer does not exist: {pointer}")
            value = value[token]
        elif isinstance(value, list):
            value = value[_array_index(token, len(value))]
        else:
            raise SaveToolError(f"JSON Pointer crosses a scalar value: {pointer}")
    return value


def _parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = parse_pointer(pointer)
    if not parts:
        raise SaveToolError("the save root cannot be modified directly")
    parent_pointer = (
        "/" + "/".join(escape_pointer(part) for part in parts[:-1]) if len(parts) > 1 else ""
    )
    return resolve(document, parent_pointer), parts[-1]


def _numeric(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, RawNumber):
            return Decimal(value.text)
        if isinstance(value, (int, float)):
            return Decimal(str(value))
    except InvalidOperation:
        return None
    return None


def json_equal(left: Any, right: Any) -> bool:
    left_number = _numeric(left)
    right_number = _numeric(right)
    if left_number is not None or right_number is not None:
        return left_number is not None and right_number is not None and left_number == right_number
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            map(lambda pair: json_equal(*pair), zip(left, right, strict=True))
        )
    return left == right


def _add(document: Any, pointer: str, value: Any) -> None:
    parent, token = _parent(document, pointer)
    if isinstance(parent, dict):
        parent[token] = copy.deepcopy(value)
    elif isinstance(parent, list):
        parent.insert(_array_index(token, len(parent), add=True), copy.deepcopy(value))
    else:
        raise SaveToolError(f"add target parent is a scalar: {pointer}")


def _remove(document: Any, pointer: str) -> Any:
    parent, token = _parent(document, pointer)
    if isinstance(parent, dict):
        if token not in parent:
            raise SaveToolError(f"remove target does not exist: {pointer}")
        return parent.pop(token)
    if isinstance(parent, list):
        return parent.pop(_array_index(token, len(parent)))
    raise SaveToolError(f"remove target parent is a scalar: {pointer}")


def _replace(document: Any, pointer: str, value: Any) -> None:
    parent, token = _parent(document, pointer)
    if isinstance(parent, dict):
        if token not in parent:
            raise SaveToolError(f"replace target does not exist: {pointer}")
        parent[token] = copy.deepcopy(value)
        return
    if isinstance(parent, list):
        parent[_array_index(token, len(parent))] = copy.deepcopy(value)
        return
    raise SaveToolError(f"replace target parent is a scalar: {pointer}")


def apply_patch(document: dict[str, Any], operations: list[Any]) -> dict[str, Any]:
    if len(operations) > 10_000:
        raise SaveToolError("patch exceeds the 10,000-operation safety limit")
    result = copy.deepcopy(document)
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise SaveToolError(f"patch operation {index} must be an object")
        name = operation.get("op")
        pointer = operation.get("path")
        if not isinstance(name, str) or not isinstance(pointer, str):
            raise SaveToolError(f"patch operation {index} requires string 'op' and 'path'")
        try:
            if name == "add":
                if "value" not in operation:
                    raise SaveToolError("add requires 'value'")
                _add(result, pointer, operation["value"])
            elif name == "remove":
                _remove(result, pointer)
            elif name == "replace":
                if "value" not in operation:
                    raise SaveToolError("replace requires 'value'")
                _replace(result, pointer, operation["value"])
            elif name == "test":
                if "value" not in operation:
                    raise SaveToolError("test requires 'value'")
                if not json_equal(resolve(result, pointer), operation["value"]):
                    raise SaveToolError(f"test failed at {pointer}")
            elif name in {"copy", "move"}:
                source = operation.get("from")
                if not isinstance(source, str):
                    raise SaveToolError(f"{name} requires string 'from'")
                value = copy.deepcopy(resolve(result, source))
                if name == "move":
                    _remove(result, source)
                _add(result, pointer, value)
            else:
                raise SaveToolError(f"unsupported patch operation: {name!r}")
        except SaveToolError as exc:
            raise SaveToolError(f"patch operation {index}: {exc}") from exc
    return result


def walk(value: Any, pointer: str = "") -> Iterator[tuple[str, str | None, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_pointer = f"{pointer}/{escape_pointer(key)}"
            yield child_pointer, key, child
            yield from walk(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_pointer = f"{pointer}/{index}"
            yield child_pointer, None, child
            yield from walk(child, child_pointer)


def find_matches(
    document: Any,
    *,
    key_pattern: str | None,
    value_pattern: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], bool]:
    try:
        key_re = re.compile(key_pattern) if key_pattern is not None else None
        value_re = re.compile(value_pattern) if value_pattern is not None else None
    except re.error as exc:
        raise SaveToolError(f"invalid regular expression: {exc}") from exc
    if key_re is None and value_re is None:
        raise SaveToolError("find requires --key and/or --value")
    matches: list[dict[str, Any]] = []
    truncated = False
    for pointer, key, value in walk(document):
        key_matches = key_re is None or (key is not None and key_re.search(key) is not None)
        scalar = not isinstance(value, (dict, list))
        rendered = scalar_text(value) if scalar else None
        value_matches = value_re is None or (rendered is not None and value_re.search(rendered))
        if key_matches and value_matches:
            if len(matches) == limit:
                truncated = True
                break
            matches.append(
                {
                    "path": pointer,
                    "key": key,
                    "type": value_type(value),
                    **({"value": value} if scalar else {}),
                }
            )
    return matches, truncated


def scalar_text(value: Any) -> str:
    if isinstance(value, RawNumber):
        return value.text
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def value_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    return "number"


@dataclass
class DiffCollector:
    limit: int
    changes: list[dict[str, Any]]
    truncated: bool = False

    def add(self, change: dict[str, Any]) -> None:
        if len(self.changes) >= self.limit:
            self.truncated = True
        else:
            self.changes.append(change)


def diff_values(left: Any, right: Any, *, pointer: str = "", limit: int = 1000) -> DiffCollector:
    result = DiffCollector(limit=limit, changes=[])

    def compare(a: Any, b: Any, path: str) -> None:
        if result.truncated or json_equal(a, b):
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() - b.keys()):
                result.add({"op": "remove", "path": f"{path}/{escape_pointer(key)}"})
            for key in sorted(b.keys() - a.keys()):
                result.add({"op": "add", "path": f"{path}/{escape_pointer(key)}", "value": b[key]})
            for key in sorted(a.keys() & b.keys()):
                compare(a[key], b[key], f"{path}/{escape_pointer(key)}")
            return
        if isinstance(a, list) and isinstance(b, list):
            for index in range(min(len(a), len(b))):
                compare(a[index], b[index], f"{path}/{index}")
            for index in range(len(a) - 1, len(b) - 1, -1):
                result.add({"op": "remove", "path": f"{path}/{index}"})
            for index in range(len(a), len(b)):
                result.add({"op": "add", "path": f"{path}/-", "value": b[index]})
            return
        result.add({"op": "replace", "path": path, "value": b})

    compare(left, right, pointer)
    return result
