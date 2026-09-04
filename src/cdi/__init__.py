"""
.. include:: ../../README.md
"""

from . import policy
from ._typing import InjectableMetadata
from ._container import Container
from ._exceptions import (
    CdiError,
    IncorrectStackPopping,
    CircularDependencyError,
    TypeEvaluationError,
)
from ._scope import Scope
from ._builtins import Lazy, Transient
from ._decorators import Injectable


__all__ = (
    "Container",
    "Scope",
    "Injectable",
    "InjectableMetadata",
    "Lazy",
    "policy",
    "Transient",
    "CdiError",
    "TypeEvaluationError",
    "IncorrectStackPopping",
    "CircularDependencyError",
)
