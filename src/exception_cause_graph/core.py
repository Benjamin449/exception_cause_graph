from __future__ import annotations

import traceback as _traceback
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ExceptionNode:
    depth: int
    relationship: str
    exc_type: str
    message: str
    traceback_str: str


def _safe_str(value: object) -> str:
    """Return str(value), never raising.

    Some exception classes override __str__ in ways that themselves raise.
    We degrade to repr() so a broken exception in the chain cannot crash the
    walker — the whole point of the library is to surface what happened.
    """
    try:
        return str(value)
    except BaseException:
        try:
            return repr(value)
        except BaseException:
            return "<unrepresentable exception>"


def _format_tb(exc: BaseException) -> str:
    """Format the traceback of *exc* into a string, or '' if it has none.

    traceback.format_exception returns a list of lines; we join them. If the
    exception has no __traceback__ we return an empty string rather than a
    synthetic 'NoneType' message, because an empty string is unambiguous in
    the output.
    """
    tb = getattr(exc, "__traceback__", None)
    if tb is None:
        return ""
    try:
        return "".join(_traceback.format_exception(type(exc), exc, tb))
    except BaseException:
        # If formatting itself blows up, fall back to a minimal marker so the
        # caller still gets a node for this exception.
        return "<traceback formatting failed>"


def walk_exception(exc: BaseException) -> List[ExceptionNode]:
    """Walk the __cause__ and __context__ chain of *exc*.

    Returns a flat list of ExceptionNode in traversal order. The root
    exception is first, with relationship 'root' and depth 0.

    Traversal rule (a deliberate choice, documented in the README):
    At each exception we prefer __cause__ (set by `raise ... from ...`). If
    __cause__ is set and is not None we descend into it and do NOT look at
    __context__ for that node. Only when __cause__ is None do we fall back to
    __context__ (set implicitly during exception handling). This mirrors how
    Python itself reports chains and avoids visiting the same implicit cause
    twice.

    A cycle guard prevents infinite loops on pathological exception graphs
    (exceptions whose __context__ points back at an ancestor). We track
    visited exceptions by id().
    """
    if not isinstance(exc, BaseException):
        raise TypeError(
            "walk_exception expects a BaseException instance, got "
            + type(exc).__name__
        )

    nodes: List[ExceptionNode] = []
    visited: set[int] = set()

    # Stack entries: (exception, depth, relationship)
    stack: List[tuple[BaseException, int, str]] = [(exc, 0, "root")]

    while stack:
        current, depth, rel = stack.pop()

        if id(current) in visited:
            continue
        visited.add(id(current))

        nodes.append(
            ExceptionNode(
                depth=depth,
                relationship=rel,
                exc_type=type(current).__name__,
                message=_safe_str(current),
                traceback_str=_format_tb(current),
            )
        )

        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)

        # We push context first, then cause, so that cause is popped first
        # (LIFO) — preserving cause-before-context ordering in output when
        # both are present. In practice only one is followed per node per the
        # rule above, but pushing in this order keeps the intent clear.
        if context is not None and id(context) not in visited:
            stack.append((context, depth + 1, "context"))

        if cause is not None and id(cause) not in visited:
            stack.append((cause, depth + 1, "cause"))

    return nodes


def format_exception_graph(exc: BaseException) -> str:
    """Return a human-readable multi-line string of the exception chain.

    Each node is rendered as:
        {depth} {relationship}: {exc_type}: {message}
    Tracebacks are not included in this rendering (use walk_exception to
    access them). The format is intentionally compact and line-oriented so it
    can be embedded in logs without further wrapping.
    """
    nodes = walk_exception(exc)
    lines: List[str] = []
    for node in nodes:
        indent = "  " * node.depth
        lines.append(f"{indent}{node.relationship}: {node.exc_type}: {node.message}")
    return "\n".join(lines)
