import inspect
import threading
from types import ModuleType
from typing import (
    Any,
    ForwardRef,
    TypeVar,
    Generic,
    overload,
    get_origin,
    get_args,
    cast,
)
from collections.abc import Callable
from collections import defaultdict, deque

from ._scope import Scope
from ._provider import Provider
from ._consts import __skip_types__
from ._typing import (
    is_concrete_type,
    unwrap_type,
    all_typealias_variants,
    calculate_type_metric,
    forward_ref,
    evaluate_forward_ref,
    get_generics,
    is_typealias,
)


__all__ = ("Container",)

_T = TypeVar("_T")


class _TypeNode:
    def __init__(self) -> None:
        self._provider: Provider | None = None
        self._implementors: list[Any] = []

    @property
    def implementors(self) -> tuple[Any, ...]:
        return tuple(self._implementors)

    @property
    def provider(self) -> Provider | None:
        return self._provider

    def set_provider(self, provider: Provider) -> None:
        # if we do have a provider, check against the providers metrics, if the given
        # provider metric is lower it means it is better
        if self._provider is None or provider.metric < self._provider.metric:
            self._provider = provider

    def add_implementor(self, subtype: type) -> None:
        """add the given type as an implementor of the current typenode"""
        if subtype not in self._implementors:
            self._implementors.append(subtype)

    def __repr__(self) -> str:
        return f"_TypeData({self._provider!r}, {self.implementors!r})"


class Container:
    def __init__(self) -> None:
        # create a mapping between a type to the typenode, the key
        # types will always be concrete types and never expect typevar
        # if given type has typevars that are not bounded they will be replaced with `Any`
        self._entries: dict[type[Any], _TypeNode] = defaultdict(_TypeNode)
        self._forward_refs: dict[ModuleType, list[tuple[ForwardRef, Provider]]] = (
            defaultdict(list)
        )
        self._lock = threading.Lock()

    def scope(self, name: str | None = None) -> Scope:
        return Scope(container=self, name=name)

    def update_forward_ref(self, module: ModuleType) -> None:
        """
        evalutes all the forward referenced types from a module
        and adds them to the internal container tree for type provider

            def my_foo_provider() -> "Foo":
                pass

            ctr.add_provider("Foo", my_foo_provider)

            class Foo:
                pass

            # although `Foo` is not defined, we will not get provider
            # for this type because we didn't update the forward references
            # in the our container (ctr)
            assert ctr.get_provider(Foo) is None

            # update the forward references for the current
            # module after we defined the `Foo` class
            ctr.update_forward_ref(sys.modules[__name__])

            # now the `get_provider` call will return for us a provider
            # that can give us `Foo`
            assert ctr.get_provider(Foo) is not None
        """

        with self._lock:
            for fr, provider in self._forward_refs[module]:
                evaluated = evaluate_forward_ref(fr, module)
                self._add_provider(evaluated, provider)
            del self._forward_refs[module]

    def get_provider(self, type_: type[Any]) -> Provider | None:
        with self._lock:
            return self._get_provider(type_)

    def add_provider(self, type_: Any, callable: Callable[..., Any]) -> None:
        """
        adds a provider for the given type, the given type can be a typevar, type alias or
        even type that accept generics

        if the given type_ is a string, it will be treated as a forward reference and will not be
        evaluted to the real (forwarded) type until `update_forward_ref` is called

        if a typevar is passed, the typevar will be resolved based on its constraints or bounds, if the
        typevar is not bounded to anything, a TypeError will be raised because it the only
        evaluation possible is `Any` which does not make sense, so typevars will be evaluated like so

            T = TypeVar("T", int, str) # evaluted to (int, str)
            R = TypeVar("R", bound=Iterable)  # evaluted to (Iterable)
            E = TypeVar("E")  # evaluate to `Any` which result in an error

        so the given provider will be a provider for all the typevar evaluation

        if a typealias is passed, provider will be mapped 1 to one, but the an extra logic will
        be performed on the typealias to build a inheritence tree

            T = TypeVar("T")
            ctr = Container()

            class Base:
                pass

            class Foo(Base, Generic[T]):
                pass

            ctr.add_provider(Foo[int], ...)
            ctr.add_provider(Foo[str], ...)

        the internal container "tree" would look like so

                     Base
                  [no provider]
                   /       \
                  /         \
              Foo[int]     Foo[str]
              [provider]   [provider]

        this will help for generic resultion when trying to get
        a provider for a generic

        if a type that accept generics is passed and it is not a concrete type, means
        it can be a typealias that accept generics or a type that has generics

            T = TypeVar("T")
            R = TypeVar("R", int, str)

            class Foo(Base, Generic[T, R]):
                pass

            Foo <- type that accept generic T, R
            Foo[T, int] <- accept generic T

            ctr.add_provider(Foo, x)
            ctr.add_provider(Foo[T, int], y)

        the internal container tree will map all the evaluation of T
        to the given provider

                      Base
                  /           \
                 /             \
                /               \
              Foo[Any, int]   Foo[Any, str]
              [provider: y]  [provider: x]
        """
        if inspect.isclass(type_):
            provider = Provider.from_class(type_)
        else:
            provider = Provider(
                callable=callable,
                callable_args=(),
                callable_kwargs={},
                metric=calculate_type_metric(type_),
            )

        with self._lock:
            self._add_provider(type_, provider)

    def _get_provider(self, type_: Any) -> Provider | None:
        typenodes: list[_TypeNode] = []
        if not is_concrete_type(type_):
            for variant in all_typealias_variants(type_):
                # if we don't have an entry to this type variant, it means it was never
                # registered to the container, either directly via `add_provider` or
                # indirectly by a child class
                if variant not in self._entries:
                    continue

                typenode = self._entries[variant]
                typenodes.append(typenode)
        elif type_ in self._entries:
            typenode = self._entries[type_]
            if typenode.provider is not None:
                return typenode.provider
            typenodes.append(typenode)
        else:
            return None

        stack = deque(typenodes)
        best_provider: Provider | None = None

        while stack:
            typenode = stack.pop()

            if typenode.provider:
                # if the current typnode has a provider, we try to take the most specific
                # provider (the one with the lowest metric) and we don't need to continue
                # and get the the `typnode.implementors` because one way or another we
                # already have a provider
                if (
                    best_provider is None
                    or best_provider.metric > typenode.provider.metric
                ):
                    best_provider = typenode.provider
            elif not best_provider:
                # if the current typenode doesn't have a provider and we didn't find a provider
                # up until now, we should check the typenode implementors
                stack.extendleft(self._entries[t] for t in typenode.implementors)
        return best_provider

    def _add_provider(self, type_: Any, provider: Provider) -> None:
        if isinstance(type_, str):
            module = cast(ModuleType, inspect.getmodule(callable))
            self._forward_refs[module].append((forward_ref(type_), provider))
        elif isinstance(type_, TypeVar):
            if (variants := unwrap_type(type_)) == (Any,):
                raise TypeError(
                    f"given typevar `{type_}` for provider `{callable.__name__}` is not bounded or constraint"
                )
            for variant in variants:
                self._add_entry(variant).set_provider(provider)
        elif not is_concrete_type(type_):
            for variant in all_typealias_variants(type_):
                self._add_provider(variant, provider)
        elif is_typealias(type_):
            for tt in unwrap_type(type_):
                if not is_concrete_type(tt):
                    self._add_provider(tt, provider)
                else:
                    self._add_entry(tt).set_provider(provider)
        else:
            self._add_entry(type_).set_provider(provider)

    def _add_entry(self, type_: type[Any]) -> _TypeNode:
        """
        adds an entry for given type, if type already has an entry, it will
        return the existing one
        """
        if type_ in self._entries:
            return self._entries[type_]
        return self._add_type_entry(type_)

    def _add_type_entry(self, type_: type[Any]) -> _TypeNode:
        """
        add typealias entry, it is expected that the typ alias
        called when adding a typevar that doesn't take generics in
        its arguments
        """
        origin = get_origin(type_) or type_

        # create a mapping between the generics the current typealias expects and
        # to the value that was passed to the type alias
        # Foo[int, str] (Foo[T, R]) -> {"T": int, "R": str}
        # if the given type doesn't accept generics this dict will just be empty
        typevar_values = {
            g.__name__: v for g, v in zip(get_generics(origin), get_args(type_))
        }

        # remember the orig base parents `origin` so we won't iterate
        # over them when we iter our `__mro__`
        orig_base_parents = []

        for orig_base in getattr(origin, "__orig_bases__", ()):
            if not is_typealias(orig_base) or get_origin(orig_base) is Generic:
                continue

            parent_typevars = []

            # takes the parent argument that were passed, if we pass to the parent
            # a typevar, we resolve that typevar with the concrete value that was
            # passed to use, assume we are typealias, if we are not typealias, we cannot pass
            # a parent generics
            for arg in get_args(orig_base):
                if isinstance(arg, TypeVar):
                    # if the parent takes a generic, we need to convert that generic
                    # to a concrete type from our typevar values
                    parent_typevars.append(typevar_values[arg.__name__])
                else:
                    parent_typevars.append(arg)

            parent_origin = get_origin(orig_base)
            orig_base_parents.append(parent_origin)

            # add the current type as an implementor of the parent variant
            self._add_entry(parent_origin[*parent_typevars]).add_implementor(type_)

        skip_parents = (*__skip_types__, *orig_base_parents)

        for cls in origin.__bases__:
            if cls not in skip_parents:
                self._add_entry(cls).add_implementor(type_)
        return self._entries[type_]

    @overload
    def inject(self, __o: None = None, /) -> Callable[[_T], _T]: ...

    @overload
    def inject(self, __o: _T, /) -> _T: ...

    def inject(self, __o: _T | None = None, /) -> _T | Callable[[_T], _T]:
        def __inject(__o: _T, /) -> _T:
            if inspect.isclass(__o):
                self.add_provider(__o, __o)
            else:
                __o = cast(Callable[..., Any], __o)

                signature = inspect.signature(__o)
                rt = signature.return_annotation

                if rt is signature.empty:
                    raise TypeError(
                        f"decorated provider `{__o._name__}` doesn't have any return type annotation"
                    )

                if isinstance(rt, str):
                    module = inspect.getmodule(__o)
                    assert (
                        module
                    ), f"couldn't get module from injector provider `{__o.__name__}`"

                    try:
                        fr = forward_ref(rt)
                        rt = evaluate_forward_ref(fr, module)
                    except NameError:
                        # if the return type is a forward reference, we might be able to evaluate
                        # it at the spot, if not at leaset we tried
                        pass

                self.add_provider(rt, __o)
            return __o

        if __o is None:
            return __inject
        return __inject(__o)
