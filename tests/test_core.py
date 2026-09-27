import unittest

from exception_cause_graph import ExceptionNode, walk_exception, format_exception_graph


class TestWalkException(unittest.TestCase):
    def test_single_exception_root(self):
        exc = ValueError("boom")
        nodes = walk_exception(exc)
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].depth, 0)
        self.assertEqual(nodes[0].relationship, "root")
        self.assertEqual(nodes[0].exc_type, "ValueError")
        self.assertEqual(nodes[0].message, "boom")

    def test_cause_chain(self):
        try:
            raise ValueError("inner")
        except ValueError as inner:
            try:
                raise RuntimeError("outer") from inner
            except RuntimeError as outer:
                nodes = walk_exception(outer)

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].relationship, "root")
        self.assertEqual(nodes[0].message, "outer")
        self.assertEqual(nodes[1].relationship, "cause")
        self.assertEqual(nodes[1].message, "inner")
        self.assertEqual(nodes[1].depth, 1)

    def test_context_chain(self):
        try:
            raise ValueError("inner")
        except ValueError:
            try:
                raise RuntimeError("outer")
            except RuntimeError as outer:
                nodes = walk_exception(outer)

        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0].relationship, "root")
        self.assertEqual(nodes[1].relationship, "context")
        self.assertEqual(nodes[1].message, "inner")

    def test_cause_takes_precedence_over_context(self):
        # When both __cause__ and __context__ are set, __cause__ is followed.
        inner_a = ValueError("context-source")
        inner_b = TypeError("cause-source")
        try:
            raise inner_a
        except ValueError:
            try:
                raise RuntimeError("outer") from inner_b
            except RuntimeError as outer:
                nodes = walk_exception(outer)

        # root -> cause (inner_b). context (inner_a) is also pushed and since
        # it is a distinct exception it appears as a sibling at depth 1.
        rels = [n.relationship for n in nodes]
        msgs = [n.message for n in nodes]
        self.assertIn("cause", rels)
        self.assertIn("context", rels)
        self.assertEqual(nodes[0].message, "outer")
        self.assertIn("cause-source", msgs)
        self.assertIn("context-source", msgs)

    def test_traceback_string_present_when_tb_exists(self):
        try:
            raise ValueError("with-tb")
        except ValueError as exc:
            nodes = walk_exception(exc)
        self.assertIn("ValueError", nodes[0].traceback_str)
        self.assertIn("with-tb", nodes[0].traceback_str)

    def test_traceback_empty_when_no_tb(self):
        exc = ValueError("no-tb")
        nodes = walk_exception(exc)
        self.assertEqual(nodes[0].traceback_str, "")

    def test_cycle_guard(self):
        # Construct a pathological cycle: a.__context__ = b, b.__context__ = a
        a = ValueError("a")
        b = TypeError("b")
        a.__context__ = b
        b.__context__ = a
        nodes = walk_exception(a)
        # Should terminate with exactly 2 nodes, no infinite loop.
        self.assertEqual(len(nodes), 2)
        msgs = {n.message for n in nodes}
        self.assertEqual(msgs, {"a", "b"})

    def test_self_cycle_guard(self):
        a = ValueError("a")
        a.__context__ = a
        nodes = walk_exception(a)
        self.assertEqual(len(nodes), 1)

    def test_non_exception_raises_type_error(self):
        with self.assertRaises(TypeError):
            walk_exception("not an exception")  # type: ignore[arg-type]

    def test_exception_with_broken_str(self):
        class BadStr(Exception):
            def __str__(self):
                raise RuntimeError("str itself broke")

        exc = BadStr()
        nodes = walk_exception(exc)
        # Should not raise; should fall back to repr.
        self.assertEqual(nodes[0].exc_type, "BadStr")
        self.assertIn("BadStr", nodes[0].message)

    def test_returns_list_of_exception_node(self):
        exc = ValueError("x")
        nodes = walk_exception(exc)
        self.assertIsInstance(nodes, list)
        for n in nodes:
            self.assertIsInstance(n, ExceptionNode)


class TestFormatExceptionGraph(unittest.TestCase):
    def test_basic_format(self):
        try:
            raise ValueError("inner")
        except ValueError:
            try:
                raise RuntimeError("outer")
            except RuntimeError as outer:
                text = format_exception_graph(outer)

        lines = text.splitlines()
        self.assertEqual(lines[0], "root: RuntimeError: outer")
        self.assertEqual(lines[1], "  context: ValueError: inner")

    def test_format_with_cause(self):
        inner = ValueError("inner")
        try:
            raise RuntimeError("outer") from inner
        except RuntimeError as outer:
            text = format_exception_graph(outer)
        lines = text.splitlines()
        self.assertEqual(lines[0], "root: RuntimeError: outer")
        self.assertEqual(lines[1], "  cause: ValueError: inner")


class TestExceptionNode(unittest.TestCase):
    def test_node_is_frozen(self):
        node = ExceptionNode(
            depth=0,
            relationship="root",
            exc_type="ValueError",
            message="m",
            traceback_str="",
        )
        with self.assertRaises(Exception):
            node.depth = 1  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
