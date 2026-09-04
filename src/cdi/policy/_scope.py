from __future__ import annotations

import inspect
from types import GenericAlias
from typing import (
    TYPE_CHECKING,
    Any,
    Annotated,
    Generic,
    TypeVar,
    get_origin,
    get_args,
    cast,
)
from typing_extensions import TypeForm

from cdi._typing import _get_typevar_mapping, is_generic_alias

if TYPE_CHECKING:
    from cdi import Scope


_T = TypeVar("_T")


class NoFactoryPolicy:
    """
    policy that is used for scope `no_factory_policy`, the policy is called
    when the scope has no factory for an evaluated type and choose what to do in such case

    the policy accept the `Scope` and `type_` that couldn't be created and should return
    instance of the type or something that can satisfy the type, the returned instance
    will be inserted into the scope for given type `T`

    if the factory policy fails, it can raise any `Exception`
    """

    def handle(self, scope: Scope, type_: TypeForm[_T]) -> _T:
        raise NotImplementedError


class ErrorNoFactoryPolicy(NoFactoryPolicy):
    """does no evaluation of the type and raises `TypeError`"""

    def handle(self, scope: Scope, type_: TypeForm[_T]) -> _T:
        """@private"""
        raise TypeError


class EvaluateUnknownTypesPolicy(NoFactoryPolicy):
    """
    tries to evaluate the given type by looking at the type signature and parameters
    the parameters will be evaluated by the `Scope`

    ```py
    def foo(x: int) -> Foo: ...

    ctr = cdi.Container()
    scope = cdi.Scope(
        __name__,
        container=ctr,
        no_factory_policy=EvaluateUnknownTypePolicy()
    )

    # either scope or container has no `int`
    assert not scope.has_instance(int)
    assert not ctr.has_registered(int)

    scope.get_instance(Foo)

    assert scope.has_instance(Foo)

    # scope now has `int` because of the evaluation
    # of `Foo`
    assert scope.has_instance(int)
    ```
    """

    __unsupported_origins__ = (Generic,)
    __safe_builtin_types__ = (
        float,
        int,
        str,
        bool,
        tuple,
        list,
        dict,
        set,
        frozenset,
    )

    def handle(self, scope: Scope, type_: TypeForm[_T]) -> _T:
        """@private"""
        if type_ in self.__safe_builtin_types__:
            return type_()  # type: ignore

        if origin := get_origin(type_):
            if origin is Annotated:
                return scope.get_instance(origin)

            if origin in self.__unsupported_origins__:
                raise TypeError(
                    f"evaluation policy does not support evaluating generic aliases of type `{origin.__name__}`"
                )
            factory = origin
        else:
            factory = type_

        factory = cast(type, factory)

        try:
            signature = inspect.signature(factory)
        except ValueError:
            return factory()

        args = []
        kwargs = {}
        typevars = _get_typevar_mapping(type_)

        for name, parameter in signature.parameters.items():
            annotation = typevars.get(parameter.annotation, parameter.annotation)

            if is_generic_alias(parameter.annotation):
                annotation = self._evaluate_generic_parameter(
                    annotation,
                    typevars,
                )

            # we rely that the `parameter.annotation` will be supported by the scope
            # and if not, it will call the current policy again to evaluate the type
            instance = scope.get_instance(annotation)

            if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
                kwargs[name] = instance
            else:
                args.append(instance)
        return factory(*args, **kwargs)

    def _evaluate_generic_parameter(
        self, type_: GenericAlias, typevars: dict[TypeVar, Any]
    ) -> GenericAlias:
        origin = get_origin(type_)
        arguments = []

        for type_arg in get_args(type_):
            arguments.append(typevars.get(type_arg, type_arg))
        return GenericAlias(origin, tuple(arguments))
