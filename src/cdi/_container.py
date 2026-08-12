from __future__ import annotations
from types import ModuleType

from ._typing import is_forward_ref, is_typevar
from ._evaluator import FactoryParameterEvaluatorProxy, TypeModuleEvaluator
from ._factory import Factory, FactoryParameter
from ._registry import Registry


__all__ = ("Container",)


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

    @property
    def is_ready(self) -> bool:
        return not self._partially_initialized

    def register(self, factory: Factory) -> None:
        if _is_factory_valid(factory):
            self._factory.add(factory)
        else:
            self._partially_initialized.append(factory)

    def get_factory(self, type_: type) -> Factory | None:
        return self._factory.get(type_)

    def update_forward_ref(self, module: ModuleType) -> None:
        partially_initialized = []

        for factory in self._partially_initialized:
            if factory.module is not module:
                partially_initialized.append(factory)
                continue

            for name, parameter in factory.parameters.items():
                if not is_forward_ref(parameter.annotation):
                    continue

                annotation = FactoryParameterEvaluatorProxy(
                    factory=factory, evaluator=TypeModuleEvaluator(parameter.module)
                ).evaluate((name, parameter))
                factory.set_parameter(
                    name,
                    FactoryParameter(
                        annotation=annotation,
                        kind=parameter.kind,
                        module=parameter.module,
                    ),
                )
            self._factory.add(factory)
        self._partially_initialized = partially_initialized
