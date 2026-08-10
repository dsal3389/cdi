from __future__ import annotations

from ._factory import Factory
from ._registry import Registry
from ._typing import is_forward_ref, is_typevar


__all__ = (
    "Container",
)


def _is_factory_valid(factory: Factory) -> bool:
    if is_forward_ref(factory.return_type) or is_typevar(factory.return_type):
        return False

    for parameter in factory.parameters.values():
        if is_forward_ref(parameter.annotation) or is_typevar(parameter.annotation):
            return False
    return True


class Container:
    def __init__(self) -> None:
        self._factory: Registry[Factory] = Registry(lambda factory: factory.return_type)
        self._partially_initialized: list[Factory] = []

    def register(self, factory: Factory) -> None:
        if _is_factory_valid(factory):
            self._factory.add(factory)
        else:
            self._partially_initialized.append(factory)

    def get_factory(self, type_: type) -> Factory | None:
        return self._factory.get(type_)

    def update_forward_ref(self) -> None:
        pass
