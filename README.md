# exception-cause-graph

Walks the `__cause__` and `__context__` chains of a Python exception instance and produces a flat list of `(type, message, traceback)` tuples annotated with depth and relationship labels (`root`, `cause`, `context`).

## Usage

```python
from exception_cause_graph import walk_exception, format_exception_graph

try:
    raise ValueError("disk missing")
except ValueError:
    try:
        raise RuntimeError("startup failed")
    except RuntimeError as exc:
        for node in walk_exception(exc):
            print(node.depth, node.relationship, node.exc_type, node.message)

        print(format_exception_graph(exc))
```

`walk_exception(exc)` returns a `list[ExceptionNode]`. Each `ExceptionNode` has fields `depth` (int), `relationship` (str), `exc_type` (str), `message` (str), `traceback_str` (str).

`format_exception_graph(exc)` returns a compact multi-line string with one line per node, indented by depth.

## Why

Logging an exception usually gives you the outermost type and message. The actual cause is often one or two `__context__` / `__cause__` hops away, and `traceback.format_exception` produces a wall of text that is hard to search programmatically. This library gives you a flat, structured list you can iterate, filter, or log line by line.

The trade-off: the output is not a re-raisable exception tree. It is a read-only summary. If you need to re-raise, use the original exception.

## Edge cases

- **Cause vs. context precedence.** When a node has both `__cause__` (set by `raise X from Y`) and `__context__` (set implicitly during handling), both are followed as separate children. This is deliberate: the library surfaces the full graph rather than hiding one branch. If you only want the Python interpreter's "suppressed" semantics, filter by `relationship`.
- **Cycles.** Exceptions whose `__context__` points back at an ancestor are guarded by an `id()`-based visited set. The walker terminates; you get each exception once.
- **Broken `__str__`.** If an exception's `__str__` raises, the walker falls back to `repr()` so a broken exception cannot crash the walk.
- **No traceback.** An exception with no `__traceback__` (e.g. constructed but never raised) yields an empty `traceback_str`, not a synthetic placeholder.
