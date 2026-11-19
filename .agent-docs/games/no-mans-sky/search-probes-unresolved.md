# Remote Arena rank coverage

Search Probes targets public NMS 7.14 (Steam build `26540391`). The native rank function, its fork
IDs and its class-weight table are checked against this executable before Arena results are used.

For creatures whose adult size class follows directly from generated role data, the mod calculates
the rank tuple. Some eligible aquatic creatures also scale with their eventual spawn depth. A remote
planet query does not establish which depths and placements actually occur, so the mod evaluates the
four possible adult size classes and returns an unresolved result when those outcomes disagree with
the selected ranks. It does not treat a hypothetical class as a confirmed match.

This is conservative query coverage, not evidence that the 7.14 rank binding is broken. Removing the
unresolved result requires a placement calculation integrated into ordinary searches and checked
against in-game observations.
