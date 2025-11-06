from ._scope import Scope
from ._container import Container
from ._exceptions import CdiException, MissingAnnotation
from ._types import Fixture, Factory, Lazy

defaultc = Container()

__all__ = (
    "Scope",
    "Container",
    "CdiException",
    "MissingAnnotation",
    "Fixture",
    "Factory",
    "Lazy",
    "defaultc",
)
