"""Split Python source code into beginner-sized logical blocks.

Why this exists: sending raw code to an LLM and asking for "line by line"
explanations produces drifting line numbers and hallucinated lines. Instead we
use Python's own `ast` module to cut the file into real logical blocks first,
then ask the model to explain each block by ID. Line numbers stay exact because
Python computed them, not the model.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

_COMPOUND_NAMES = (
    "FunctionDef",
    "AsyncFunctionDef",
    "ClassDef",
    "For",
    "AsyncFor",
    "While",
    "If",
    "With",
    "AsyncWith",
    "Try",
    "TryStar",
    "Match",
)

COMPOUND_NODES = tuple(
    node
    for node in (getattr(ast, name, None) for name in _COMPOUND_NAMES)
    if node is not None
)

_KIND_LABELS = {
    "FunctionDef": "function",
    "AsyncFunctionDef": "async function",
    "ClassDef": "class",
    "For": "loop",
    "AsyncFor": "loop",
    "While": "loop",
    "If": "decision",
    "With": "context",
    "AsyncWith": "context",
    "Try": "error handling",
    "TryStar": "error handling",
    "Match": "match",
    "Import": "import",
    "ImportFrom": "import",
    "Assign": "assignment",
    "AnnAssign": "assignment",
    "AugAssign": "assignment",
    "Return": "return",
    "Expr": "action",
    "Raise": "raise",
    "Assert": "check",
    "Global": "scope",
    "Nonlocal": "scope",
    "Pass": "placeholder",
    "Break": "loop control",
    "Continue": "loop control",
    "Delete": "delete",
}


@dataclass
class Block:
    """One explainable chunk of source code."""

    id: int
    start_line: int
    end_line: int
    kind: str
    depth: int
    source: str

    @property
    def line_label(self) -> str:
        if self.start_line == self.end_line:
            return f"Line {self.start_line}"
        return f"Lines {self.start_line}-{self.end_line}"

    def to_prompt_chunk(self) -> str:
        return (
            f"<block id=\"{self.id}\" lines=\"{self.start_line}-{self.end_line}\" "
            f"kind=\"{self.kind}\">\n{self.source}\n</block>"
        )


def _kind(node: ast.AST) -> str:
    return _KIND_LABELS.get(type(node).__name__, "statement")


def _node_start(node: ast.AST) -> int:
    starts = [getattr(node, "lineno", 1)]
    for decorator in getattr(node, "decorator_list", []) or []:
        starts.append(decorator.lineno)
    return min(starts)


def _child_statements(node: ast.AST) -> List[ast.stmt]:
    """Flatten every statement nested directly inside a compound node."""
    children: List[ast.stmt] = []
    for field_name in ("body", "handlers", "orelse", "finalbody", "cases"):
        for item in getattr(node, field_name, []) or []:
            if isinstance(item, ast.stmt):
                children.append(item)
            elif hasattr(item, "body"):  # ExceptHandler, match_case
                children.extend(item.body)
    return sorted(children, key=_node_start)


class _Splitter:
    def __init__(self, source: str, max_inline_lines: int) -> None:
        self.lines = source.splitlines()
        self.max_inline = max_inline_lines
        self.blocks: List[Block] = []
        self.cursor = 1  # first line not yet assigned to a block
        self.pending_comment_start: Optional[int] = None

    # -- helpers ---------------------------------------------------------
    def _add(self, start: int, end: int, kind: str, depth: int) -> None:
        if self.pending_comment_start is not None and self.pending_comment_start < start:
            start = self.pending_comment_start
        self.pending_comment_start = None
        end = max(start, end)
        self.blocks.append(
            Block(
                id=len(self.blocks) + 1,
                start_line=start,
                end_line=end,
                kind=kind,
                depth=depth,
                source="\n".join(self.lines[start - 1 : end]),
            )
        )
        self.cursor = end + 1

    def _flush_gap(self, upto: int, attach_to_next: bool, depth: int = 0) -> None:
        """Handle lines between blocks: comments, `else:`, `except ...:` etc."""
        if upto < self.cursor:
            return
        segment = self.lines[self.cursor - 1 : upto]
        stripped = [line.strip() for line in segment]
        if not any(stripped):
            self.cursor = upto + 1
            return

        first = next(i for i, text in enumerate(stripped) if text)
        last = max(i for i, text in enumerate(stripped) if text)
        start = self.cursor + first
        end = self.cursor + last
        comments_only = all(
            (not text) or text.startswith("#") for text in stripped[first : last + 1]
        )

        if comments_only and attach_to_next:
            # Glue the comment onto the block it documents.
            self.pending_comment_start = start
            self.cursor = upto + 1
            return

        self._add(start, end, "note" if comments_only else "clause", max(0, depth - 1))
        self.cursor = max(self.cursor, upto + 1)

    # -- traversal -------------------------------------------------------
    def _walk(self, statements: List[ast.stmt], depth: int) -> None:
        for node in statements:
            start = _node_start(node)
            self._flush_gap(start - 1, attach_to_next=True, depth=depth)
            end = getattr(node, "end_lineno", None) or start
            children = _child_statements(node)
            span = end - start + 1

            is_splittable = (
                isinstance(node, COMPOUND_NODES)
                and children
                and span > self.max_inline
            )
            if is_splittable:
                first_child = min(_node_start(child) for child in children)
                self._add(start, first_child - 1, f"{_kind(node)} header", depth)
                self._walk(children, depth + 1)
                self._flush_gap(end, attach_to_next=False, depth=depth + 1)
            else:
                self._add(start, end, _kind(node), depth)

    def run(self, tree: ast.Module) -> List[Block]:
        self._walk(tree.body, depth=0)
        self._flush_gap(len(self.lines), attach_to_next=False)
        return self.blocks


_UNMERGEABLE = ("header", "clause", "unparsed")


def _mergeable(first: Block, second: Block) -> bool:
    if first.depth != second.depth:
        return False
    for block in (first, second):
        if any(marker in block.kind for marker in _UNMERGEABLE):
            return False
    # Only merge things that sit right next to each other.
    return second.start_line - first.end_line <= 2


def _merge_adjacent(blocks: List[Block], lines: List[str], target: int) -> List[Block]:
    """Combine neighbouring simple statements until we are under `target`.

    A 200-line flat script would otherwise become 200 separate API calls.
    """
    while len(blocks) > target:
        merged: List[Block] = []
        index = 0
        changed = False
        while index < len(blocks):
            current = blocks[index]
            nxt = blocks[index + 1] if index + 1 < len(blocks) else None
            if nxt is not None and _mergeable(current, nxt):
                merged.append(
                    Block(
                        id=0,
                        start_line=current.start_line,
                        end_line=nxt.end_line,
                        kind="steps",
                        depth=current.depth,
                        source="\n".join(
                            lines[current.start_line - 1 : nxt.end_line]
                        ),
                    )
                )
                index += 2
                changed = True
            else:
                merged.append(current)
                index += 1
        blocks = merged
        if not changed:
            break
    for position, block in enumerate(blocks, start=1):
        block.id = position
    return blocks


def split_blocks(
    source: str, max_blocks: int = 60
) -> Tuple[List[Block], Optional[str]]:
    """Return (blocks, syntax_error_message).

    If the code does not parse we still return one block containing everything,
    so the user gets an explanation plus a clear note about the syntax error.
    """
    source = source.rstrip()
    if not source.strip():
        return [], None

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        message = f"Line {exc.lineno}: {exc.msg}"
        fallback = Block(
            id=1,
            start_line=1,
            end_line=max(1, len(source.splitlines())),
            kind="unparsed",
            depth=0,
            source=source,
        )
        return [fallback], message

    blocks: List[Block] = []
    # Start fine-grained; coarsen only if the file would produce too many calls.
    for max_inline in (8, 14, 25, 60, 10_000):
        blocks = _Splitter(source, max_inline).run(tree)
        if len(blocks) <= max_blocks:
            break
    if len(blocks) > max_blocks:
        blocks = _merge_adjacent(blocks, source.splitlines(), max_blocks)
    return blocks, None


def blocks_to_prompt(blocks: List[Block]) -> str:
    return "\n\n".join(block.to_prompt_chunk() for block in blocks)
