"""A tiny boolean search-expression language for per-column text filters.

Turns a string like ``0603 & !0402`` into a SQLAlchemy condition on one
column. Supported syntax:

    term            case-insensitive substring match  (col ILIKE %term%)
    "two words"     quoted term (may contain spaces / operator chars)
    !term  -term    NOT (unary, binds tightest)
    a & b   a b     AND  (whitespace between terms is an implicit AND)
    a | b           OR   (lowest precedence)
    ( ... )         grouping

Precedence, tightest first: NOT, AND, OR. The word forms ``AND`` / ``OR`` /
``NOT`` are accepted as aliases for ``&`` / ``|`` / ``!``.

Design notes:
- Matching is done against ``coalesce(col, '')`` so a NULL column behaves as
  an empty string. This matters for negation: ``!0402`` must keep rows whose
  (nullable) column is NULL.
- ILIKE wildcards ``%`` and ``_`` in a term are escaped so they match
  literally.
- Parsing never raises: on a malformed expression we fall back to treating the
  whole raw string as a single literal substring term, so the UI never 500s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union

from sqlalchemy import ColumnElement, and_, func, not_, or_

# Cap input length to avoid pathological expressions from crafted queries.
MAX_EXPRESSION_LEN = 200

_OPERATOR_CHARS = {"&", "|", "!", "(", ")"}
_WORD_ALIASES = {"and": "&", "or": "|", "not": "!"}


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #
@dataclass
class Term:
    text: str


@dataclass
class Not:
    child: "Node"


@dataclass
class And:
    left: "Node"
    right: "Node"


@dataclass
class Or:
    left: "Node"
    right: "Node"


Node = Union[Term, Not, And, Or]


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
@dataclass
class _Tok:
    kind: str  # "term" | "&" | "|" | "!" | "(" | ")"
    text: str = ""


def _tokenize(text: str) -> List[_Tok]:
    tokens: List[_Tok] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _OPERATOR_CHARS:
            tokens.append(_Tok(ch))
            i += 1
            continue
        if ch == '"':  # quoted term
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                buf.append(text[j])
                j += 1
            tokens.append(_Tok("term", "".join(buf)))
            i = j + 1  # skip closing quote (or end of string)
            continue
        # bare term: read until whitespace or an operator char
        j = i
        buf = []
        while j < n and not text[j].isspace() and text[j] not in _OPERATOR_CHARS:
            buf.append(text[j])
            j += 1
        word = "".join(buf)
        alias = _WORD_ALIASES.get(word.lower())
        tokens.append(_Tok(alias) if alias else _Tok("term", word))
        i = j
    return tokens


# --------------------------------------------------------------------------- #
# Recursive-descent parser.  Grammar:
#   or   := and ( "|" and )*
#   and  := unary ( ("&")? unary )*     # implicit AND between adjacent atoms
#   unary:= "!" unary | atom
#   atom := "(" or ")" | term
# --------------------------------------------------------------------------- #
class _ParseError(Exception):
    pass


class _Parser:
    def __init__(self, tokens: List[_Tok]):
        self.toks = tokens
        self.pos = 0

    def _peek(self) -> Optional[_Tok]:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self) -> _Tok:
        tok = self.toks[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> Node:
        node = self._parse_or()
        if self.pos != len(self.toks):
            raise _ParseError("trailing tokens")
        return node

    def _parse_or(self) -> Node:
        node = self._parse_and()
        while (tok := self._peek()) and tok.kind == "|":
            self._next()
            node = Or(node, self._parse_and())
        return node

    def _parse_and(self) -> Node:
        node = self._parse_unary()
        while (tok := self._peek()) and tok.kind in ("&", "!", "(", "term"):
            if tok.kind == "&":
                self._next()  # explicit AND
            node = And(node, self._parse_unary())
        return node

    def _parse_unary(self) -> Node:
        tok = self._peek()
        if tok and tok.kind == "!":
            self._next()
            return Not(self._parse_unary())
        return self._parse_atom()

    def _parse_atom(self) -> Node:
        tok = self._peek()
        if tok is None:
            raise _ParseError("unexpected end of expression")
        if tok.kind == "(":
            self._next()
            node = self._parse_or()
            close = self._peek()
            if not close or close.kind != ")":
                raise _ParseError("unbalanced parenthesis")
            self._next()
            return node
        if tok.kind == "term":
            self._next()
            return Term(tok.text)
        raise _ParseError(f"unexpected token {tok.kind!r}")


def parse(text: str) -> Optional[Node]:
    """Parse ``text`` into an AST, or ``None`` if it holds no terms.

    On a syntax error, fall back to the whole raw string as one literal term.
    """
    tokens = _tokenize(text)
    if not any(t.kind == "term" for t in tokens):
        return None
    try:
        return _Parser(tokens).parse()
    except _ParseError:
        stripped = text.strip()
        return Term(stripped) if stripped else None


# --------------------------------------------------------------------------- #
# Compile AST -> SQLAlchemy condition
# --------------------------------------------------------------------------- #
def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _compile_node(node: Node, column: ColumnElement) -> ColumnElement:
    if isinstance(node, Term):
        haystack = func.coalesce(column, "")
        return haystack.ilike(f"%{_escape_like(node.text)}%", escape="\\")
    if isinstance(node, Not):
        return not_(_compile_node(node.child, column))
    if isinstance(node, And):
        return and_(
            _compile_node(node.left, column), _compile_node(node.right, column)
        )
    if isinstance(node, Or):
        return or_(_compile_node(node.left, column), _compile_node(node.right, column))
    raise TypeError(f"unknown node type: {type(node)!r}")  # pragma: no cover


def compile_filter(text: Optional[str], column: ColumnElement) -> Optional[ColumnElement]:
    """Compile a filter expression into a condition on ``column``.

    Returns ``None`` when ``text`` is blank or contains no terms, meaning the
    caller should apply no filter for this field.
    """
    if not text:
        return None
    ast = parse(text[:MAX_EXPRESSION_LEN])
    if ast is None:
        return None
    return _compile_node(ast, column)
