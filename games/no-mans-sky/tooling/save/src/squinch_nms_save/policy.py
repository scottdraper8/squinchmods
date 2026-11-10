from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import SaveToolError

POLICY_SCHEMA = "squinch-nms-save-policy-v1"
DEFAULT_OWNED_BASE_TYPES = frozenset(
    {
        "HomePlanetBase",
        "FreighterBase",
        "PlayerSpaceBase",
        "PlayerShipBase",
        "PlayerSpaceStationBase",
    }
)
DEFAULT_PORTABLE_BASE_TYPES = frozenset({"FreighterBase", "PlayerShipBase"})


@dataclass(frozen=True)
class Classification:
    rule: str | None
    category: str
    galaxies: tuple[int, int] | None


@dataclass(frozen=True)
class Rule:
    identifier: str
    pattern: re.Pattern[str]
    category: str
    galaxies: tuple[int, int] | None
    galaxy_groups: tuple[int, int] | None

    def match(self, name: str) -> Classification | None:
        match = self.pattern.fullmatch(name.strip())
        if match is None:
            return None
        galaxies = self.galaxies
        if self.galaxy_groups is not None:
            first_group, last_group = self.galaxy_groups
            try:
                galaxies = (int(match.group(first_group)), int(match.group(last_group)))
            except (IndexError, ValueError) as exc:
                raise SaveToolError(
                    f"policy rule {self.identifier!r} has invalid galaxy capture groups"
                ) from exc
        if galaxies is not None:
            first, last = galaxies
            if not 1 <= first <= last <= 256:
                raise SaveToolError(
                    f"policy rule {self.identifier!r} resolved invalid galaxy range {first}-{last}"
                )
        return Classification(self.identifier, self.category, galaxies)


@dataclass(frozen=True)
class SavePolicy:
    rules: tuple[Rule, ...]
    owned_base_types: frozenset[str]
    portable_base_types: frozenset[str]
    source: str
    sha256: str

    @classmethod
    def default(cls) -> SavePolicy:
        rules = (
            Rule(
                "named-galaxy-range",
                re.compile(r"Galaxies\s+(\d+)-(\d+)", re.IGNORECASE),
                "galaxy-range",
                None,
                (1, 2),
            ),
            Rule(
                "named-single-galaxy",
                re.compile(r"Galaxy\s+(\d+)(?:\s.*)?", re.IGNORECASE),
                "single-galaxy-special",
                None,
                (1, 1),
            ),
        )
        canonical = {
            "schema": POLICY_SCHEMA,
            "rules": [rule.identifier for rule in rules],
            "owned_base_types": sorted(DEFAULT_OWNED_BASE_TYPES),
            "portable_base_types": sorted(DEFAULT_PORTABLE_BASE_TYPES),
        }
        digest = hashlib.sha256(
            json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        return cls(
            rules,
            DEFAULT_OWNED_BASE_TYPES,
            DEFAULT_PORTABLE_BASE_TYPES,
            "builtin",
            digest,
        )

    @classmethod
    def load(cls, path: Path | None) -> SavePolicy:
        if path is None:
            return cls.default()
        resolved = path.expanduser().resolve()
        try:
            raw = resolved.read_bytes()
            value = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SaveToolError(f"cannot read save policy {resolved}: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema") != POLICY_SCHEMA:
            raise SaveToolError(f"policy must use schema {POLICY_SCHEMA!r}")
        raw_rules = value.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise SaveToolError("policy requires a nonempty rules array")
        rules = tuple(_parse_rule(rule, index) for index, rule in enumerate(raw_rules))
        owned = _string_set(value.get("owned_base_types"), "owned_base_types")
        portable = _string_set(value.get("portable_base_types"), "portable_base_types")
        if not portable <= owned:
            raise SaveToolError("portable_base_types must be a subset of owned_base_types")
        return cls(rules, owned, portable, str(resolved), hashlib.sha256(raw).hexdigest())

    def classify(self, name: str) -> Classification:
        matches = [result for rule in self.rules if (result := rule.match(name)) is not None]
        if len(matches) > 1:
            identifiers = ", ".join(result.rule or "" for result in matches)
            raise SaveToolError(f"save name {name!r} matches multiple policy rules: {identifiers}")
        if matches:
            return matches[0]
        return Classification(None, "non-galaxy-centric" if name.strip() else "unnamed", None)


def _string_set(value: Any, label: str) -> frozenset[str]:
    if not isinstance(value, list) or not value:
        raise SaveToolError(f"policy {label} must be a nonempty string array")
    if any(not isinstance(item, str) or not item for item in value):
        raise SaveToolError(f"policy {label} must contain only nonempty strings")
    if len(set(value)) != len(value):
        raise SaveToolError(f"policy {label} contains duplicates")
    return frozenset(value)


def _parse_rule(value: Any, index: int) -> Rule:
    if not isinstance(value, dict):
        raise SaveToolError(f"policy rule {index} must be an object")
    identifier = value.get("id")
    pattern_text = value.get("save_name_regex")
    category = value.get("category")
    if not all(isinstance(item, str) and item for item in (identifier, pattern_text, category)):
        raise SaveToolError(f"policy rule {index} requires string id, save_name_regex, category")
    try:
        pattern = re.compile(pattern_text, re.IGNORECASE)
    except re.error as exc:
        raise SaveToolError(f"policy rule {identifier!r} has invalid regex: {exc}") from exc
    fixed = value.get("galaxies")
    groups = value.get("galaxy_groups")
    if (fixed is None) == (groups is None):
        raise SaveToolError(
            f"policy rule {identifier!r} requires exactly one of galaxies or galaxy_groups"
        )
    galaxies = (
        _integer_pair(fixed, f"policy rule {identifier!r} galaxies") if fixed is not None else None
    )
    galaxy_groups = (
        _integer_pair(groups, f"policy rule {identifier!r} galaxy_groups")
        if groups is not None
        else None
    )
    return Rule(identifier, pattern, category, galaxies, galaxy_groups)


def _integer_pair(value: Any, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
    ):
        raise SaveToolError(f"{label} must be an array of two integers")
    return value[0], value[1]
