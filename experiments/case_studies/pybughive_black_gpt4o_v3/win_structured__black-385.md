# Case Study: `black-385`
**Category**: win_structured  |  **Outcome (structured)**: PASS

## Buggy Code
```python

```

## Raw Failure Signal
```
Original buggy code unexpectedly passed the configured test steps.
```

## Structured Failure State
- **failure_mode**: `assertion`
- **exception_type**: ``
- **test_name**: ``
- **contract_tags**: `['ordering', 'edge_case', 'whitespace', 'type_mismatch', 'graph_dependency', 'collection_update', 'boundary', 'recursion', 'arithmetic', 'api_usage']`
- **suspicious_symbols** (top-5): `['Original', 'buggy', 'code', 'unexpectedly', 'the']`
- **assertion_summary**: 

## Retrieval Comparison
_No code_only top-2 (before structured reranking) examples recorded._

**structured top-2 (after reranking)**

Example 1 (id=bugsinpy:black:12:black.py)
Lesson: Use the correct object attributes and preserve the local data model. Keep the base case and recursive step aligned so the fix does not change termination behavior.
```python
# buggy
"""Keeps track of brackets on a line."""

    depth: int = 0
    bracket_match: Dict[Tuple[Depth, NodeType], Leaf] = Factory(dict)
    delimiters: Dict[LeafID, Priority] = Factory(dict)
    previous: Optional[Leaf] = None
    _for_loop_variable: int = 0
    _lambda_arguments: int = 0

    def mark(s
# fixed
"""Keeps track of brackets on a line."""

    depth: int = 0
    bracket_match: Dict[Tuple[Depth, NodeType], Leaf] = Factory(dict)
    delimiters: Dict[LeafID, Priority] = Factory(dict)
    previous: Optional[Leaf] = None
    _for_loop_depths: List[int] = Factory(list)
    _lambda_argument_depths: L
```

Example 2 (id=bugsinpy:black:14:black.py)
Lesson: Use the correct object attributes and preserve the local data model. Keep the base case and recursive step aligned so the fix does not change termination behavior.
```python
# buggy
import tokenize
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Pattern,
...
yield omit
            closing_bracket = leaf


def get_future_imports(node: Node) -> Set[str]:
    """Return a set of __future__ im
# fixed
import tokenize
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generator,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Pattern,
...
yield omit
            closing_bracket = leaf


def get_future_imports(node: Node) -> Set[str]:
    """Return a set o
```

## Generated Patch (structured)
```python
import asyncio
from asyncio.base_events import BaseEventLoop
from concurrent.futures import Executor, ProcessPoolExecutor
from datetime import datetime
from enum import Enum, Flag
from functools import lru_cache, partial, wraps
import io
import keyword
import logging
from multiprocessing import Manager
import os
from pathlib import Path
import pickle
import re
import signal
import sys
import tokenize
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generator,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Pattern,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from appdirs import user_cache_dir
from attr import dataclass, Factory
import click
import toml

# lib2to3 fork
from blib2to3.pytree import Node, Leaf, type_repr

```

## Final Outcome: **PASS**
