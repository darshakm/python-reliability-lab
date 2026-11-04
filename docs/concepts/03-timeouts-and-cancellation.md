# 3. Timeouts and Cancellation

**Problem:** A request or batch can wait forever unless time is part of its
contract.

**Invariant:** Per-request timeout becomes an order-specific failure; overall
deadline terminates the batch and reports completed and pending inputs.

`TaskGroup` provides structured cleanup: sibling tasks are cancelled and awaited
before the scope exits. `CancelledError` is not converted into an ordinary
business failure.

**Does not solve:** Stopping a synchronous function already running in a thread.

**Tradeoff:** Short deadlines protect capacity but can reject work that would
eventually succeed. Budgets should follow user objectives, not arbitrary defaults.

**Explore:** Read the batch timeout tests and draw a timeline with one fast, one
timed-out, and one cancelled request.
