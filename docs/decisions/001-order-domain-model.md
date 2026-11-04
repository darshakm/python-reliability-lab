# ADR 001: Validate an immutable Order at the system boundary

- **Status:** Accepted
- **Date:** 2026-11-02
- **Scope:** Part A — Order domain model

## Context

The lab will eventually consume an unreliable orders API. External records can be
missing fields, contain surprising types, use invalid state values, or carry
ambiguous timestamps. Letting those values spread through the application would
move failures away from their source and make them harder to diagnose.

## Decision

`Order` is a frozen, slotted dataclass. It represents a value observed from an
external system, so mutation would make the object disagree with that observation.
Immutability also makes sharing an order between later concurrent components safer.

Money uses `Decimal`, not `float`, because decimal amounts should behave according
to base-10 arithmetic. Integer minor units are useful when every currency has a
fixed, known scale, but that assumption does not belong in this first general model.
The boundary parser converts incoming values using their string representation.

Status is a `Literal` union and is validated at runtime. This gives type checkers a
closed set while still rejecting invalid untyped input. Currency uses a deliberately
small syntactic check (three uppercase ASCII letters); full ISO 4217 membership and
currency-specific scale rules are deferred until business requirements demand them.

`created_at` is stored as a timezone-aware `datetime`. The parser accepts ISO 8601
`Z` or numeric offsets and rejects naive timestamps because their instant is
ambiguous.

Untrusted mappings enter through `Order.from_dict()`. It requires the exact schema,
parses boundary representations, and rejects extra fields. Direct construction is
reserved for already-typed domain values and is still protected by `__post_init__`.

## Consequences

- Invalid records fail close to the integration boundary with specific errors.
- Callers receive stable, typed, immutable values.
- Adding a field to the upstream payload will initially fail rather than pass
  silently; schema evolution must therefore be handled intentionally.
- `from_dict()` raises built-in `TypeError` and `ValueError`; `OrderClient`
  translates them into `MalformedResponseError` without coupling this domain model
  to transport code.
- HTTP behavior lives in a separate module. Retry logic remains deferred to the
  retry and rate-limiting unit.
