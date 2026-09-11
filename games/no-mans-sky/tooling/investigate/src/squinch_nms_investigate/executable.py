from __future__ import annotations

import re
from pathlib import Path

from .errors import InvestigationError
from .paths import sha256_file

ASCII = re.compile(rb"[\x20-\x7e]{4,}")


def inspect_strings(executable: Path, patterns: list[str], *, limit: int = 500) -> dict:
    if limit < 1:
        raise InvestigationError("invalid_limit", "Executable string result limit must be positive")
    try:
        compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    except re.error as exc:
        raise InvestigationError(
            "invalid_pattern", f"Invalid executable string pattern: {exc}"
        ) from exc
    matches: list[dict] = []
    pattern_counts = {pattern: 0 for pattern in patterns}
    data = executable.read_bytes()
    for found in ASCII.finditer(data):
        value = found.group().decode("ascii")
        matching = [
            patterns[index] for index, pattern in enumerate(compiled) if pattern.search(value)
        ]
        if matching:
            for pattern in matching:
                pattern_counts[pattern] += 1
            matches.append({"offset": found.start(), "value": value[:1000], "patterns": matching})
    return {
        "executable": str(executable),
        "bytes": len(data),
        "sha256": sha256_file(executable),
        "patterns": patterns,
        "pattern_counts": pattern_counts,
        "all_patterns_matched": all(pattern_counts.values()),
        "match_count": len(matches),
        "matches": matches[:limit],
        "matches_truncated": len(matches) > limit,
        "authority": "static-printable-strings",
    }
