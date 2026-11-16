# Tooling ownership

The parent repository owns cross-product orchestration: scratch tranches, game and dependency
discovery, controlled launch and teardown, build invocation, deployment, runtime-protocol clients,
evidence retention, and operator-facing presentation. These tools live outside mod submodules and
are dispatched through `tooling/squinch`.

Each mod repository remains a complete standalone product. It owns source compilation, unit and
integration tests, package construction, product-specific policy checks, and release validation.
Code that must execute inside a game process also belongs to the mod, but it exposes only a small,
versioned local protocol. The parent owns capability negotiation and workflows that consume that
protocol.

This boundary is enforced through observable product and protocol behavior, not filename allowlists.
Each mod's own CI must build and validate it without the parent repository. Parent-side protocol
clients fail closed on unknown protocol versions and capabilities, while provider and consumer tests
cover their respective contracts. Changes that alter both sides require a live compatibility check
before either side is released.

Search Probes is the first capability-negotiated runtime. Its in-process provider owns qualified NMS
memory access and native classification. The parent NMS investigation client validates the live
instance, negotiates `search.control/v1` or `nms.current-world/v1`, submits bounded requests, and
retains/presents the returned facts. A legacy schema-1 endpoint advertises search control only;
unknown endpoint or protocol versions fail closed.
