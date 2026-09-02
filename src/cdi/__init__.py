"""
.. include:: ../../README.md
"""

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
    "Scope",
    "Container",
    "Injectable",
    "InjectableMetadata",
    "Lazy",
    "Transient",
    "CdiError",
    "TypeEvaluationError",
    "IncorrectStackPopping",
    "CircularDependencyError",
)
