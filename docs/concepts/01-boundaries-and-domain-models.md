# 1. Boundaries and Domain Models

**Problem:** External JSON is untrusted and can spread ambiguity into the system.

**Invariant:** Code beyond the boundary receives a valid immutable `Order` or a
specific error—never a partially trusted dictionary.

`OrderClient` owns HTTP and JSON parsing. `Order.from_dict()` owns domain shape,
money, status, identifiers, and timezone-aware timestamps. `Decimal` preserves
base-10 monetary meaning; a frozen dataclass prevents downstream mutation of an
observed value.

**Does not solve:** Schema version negotiation or business authorization.

**Tradeoff:** Exact-field validation exposes drift immediately but makes additive
upstream fields breaking until the policy changes intentionally.

**Explore:** Read `models.py`, `client.py`, and their negative tests. Propose a
policy for unknown fields and explain what observability replaces strict failure.
