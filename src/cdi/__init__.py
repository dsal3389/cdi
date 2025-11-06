from ._scope import Scope
from ._container import Container
from ._exceptions import CdiException, MissingAnnotation

defaultc = Container()

__all__ = ("Scope", "Container", "CdiException", "MissingAnnotation", "defaultc")
