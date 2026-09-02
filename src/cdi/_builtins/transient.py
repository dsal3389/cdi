from typing import TypeVar, Annotated
from cdi._typing import InjectableMetadata


__all__ = (
    "Transient",
)

_T = TypeVar("_T")

Transient = Annotated[_T, InjectableMetadata(transient=True)]
"""
used for conviniance and for clearer and nicer code, to read more about `Transient` refer to `cdi.InjectableMetadata`
"""
