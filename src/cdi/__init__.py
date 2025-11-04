import inspect
import itertools
import threading
from types import UnionType, ModuleType
from typing import (
    Any,
    ForwardRef,
    TypeVar,
    Union,
    Annotated,
    Generic,
    cast,
    get_origin,
    get_args,
    overload,
)
from collections.abc import Callable
from collections import defaultdict


T = TypeVar("T")
_I = TypeVar("_I")

_Fixture = object()
_Factory = object()

Fixture = Annotated[T, _Fixture]
Factory = Annotated[T, _Factory]


__skip_types__ = (object, Generic)


def _is_typealias(type_: Any) -> bool:
    return get_origin(type_) is not None and len(get_args(type_)) > 0


def _is_fixture_annotation(anno: type[Any]) -> bool:
    return _Fixture in get_args(anno)


def _is_factory_annotation(anno: type[Any]) -> bool:
    return _Factory in get_args(anno)


def _has_typevars(type_: Any) -> bool:
    """
    returns a boolean value indicating if given type has at least 1 typevar instead of concrete types

        T = TypeVar("T")
        R = TypeVar("R")

        class Foo(Generic[T, R]):
            pass

        assert not _has_typevars(Foo)
        assert not _has_typevars(Foo[int, int])
        assert _has_typevars(Foo[int, T])
    """
    for arg in get_args(type_):
        if isinstance(arg, TypeVar):
            return True
    return False


def _get_typevars(type_: Any) -> tuple[TypeVar, ...]:
    """
    returns the typevars that were passed to the type as arguments

        T = TypeVar("T")
        R = TypeVar("R")
        F = TypeVar("F")

        class Foo(Generic[T, R]):
            pass

        assert _get_typevars(Foo[str, str]) == ()
        assert _get_typevars(Foo[T, str]) == (T)
        assert _get_typevars(Foo[str, T]) == (T)
        assert _get_typevars(Foo[T, R]) == (T, R)
        assert _get_typevars(Foo[F, T]) == (F, T)
        assert _get_typevars(Foo) == ()
    """
    if not _is_typealias(type_):
        return ()
    return tuple(filter(lambda arg: isinstance(arg, TypeVar), get_args(type_)))


def _get_generics(type_: Any) -> tuple[TypeVar, ...]:
    """
    if given type expect generics, this function will returns the generics it expects
    without considering what was passed in its arguments

        T = TypeVar("T")
        R = TypeVar("R")
        F = TypeVar("F")

        class Foo(Generic[T, R]):
            pass

        assert _get_generics(Foo[int, str]) == (T, R)
        assert _get_generics(Foo[F, str]) == (T, R)
        assert _get_generics(Foo) == (T, R)
    """
    if _is_typealias(type_):
        type_ = get_origin(type_)

    for orig_base in getattr(type_, "__orig_bases__", []):
        if _is_typealias(orig_base) and get_origin(orig_base) is Generic:
            return get_args(orig_base)
    return ()


def _is_concrete_type(type_: Any) -> bool:
    """
    returns a boolean value indicating if the given type is a concrete type
    or it takes generics
    """
    # if the given type has generics, we check, if its a type alias (if not its not concrete type because it doesn't has args)
    # and we check that it doesn't have typevars in its args
    return (
        (_get_generics(type_) == ())
        or _is_typealias(type_)
        and not _has_typevars(type_)
    )


def _is_union(type_: Any) -> bool:
    if _is_typealias(type_):
        type_ = cast(Any, get_origin(type_))
    return type_ is Union or type_ is UnionType


def _get_typevar_variants(typevar: TypeVar) -> tuple[Any, ...]:
    if typevar.__bound__:
        return _unwrap_type(typevar.__bound__)
    return typevar.__constraints__ or (Any,)


def _unwrap_type(type_: Any) -> tuple[Any, ...]:
    """
    unwrap annotation types and generics to their concrete types

        T = TypeVar("T")
        R = TypeVar("R", bound=str | int)

        assert _unwrap_type(str | int) == (str, int)
        assert _unwrap_type(str | int | Annotated[list[str]]) == (str, int, list[str])
        assert _unwrap_type(str | int | Annotated[list[str]], group_unions=True) == ((str, int, list[str]),)
        assert _unwrap_type(T) == (Any,)
        assert _unwrap_type(T | R) == (Any, str, int)
    """
    if _is_typealias(type_):
        if _is_union(type_):
            unwraped_map = map(_unwrap_type, get_args(type_))
            return tuple(itertools.chain.from_iterable(unwraped_map))

        origin = get_origin(type_)

        if origin is Annotated:
            anno_type, *_ = get_args(type_)
            return _unwrap_type(anno_type)
        if origin is Generic:
            variants_map = map(_get_typevar_variants, get_args(type_))
            return tuple(itertools.chain.from_iterable(variants_map))

    if isinstance(type_, TypeVar):
        return _get_typevar_variants(type_)
    return (type_,)


def _all_typealias_variants(type_: Any) -> tuple[Any, ...]:
    origin = get_origin(type_) or type_
    generic_variants: list[tuple[Any, ...]] = []

    if args := get_args(type_):
        for arg in args:
            generic_variants.append(_unwrap_type(arg))
    else:
        # unwrap all the generics to their concrete types
        for generic_arg in _get_generics(origin):
            generic_variants.append(_unwrap_type(generic_arg))

    variants = []
    for variant in itertools.product(*generic_variants, repeat=1):
        variants.append(origin[*variant])  # type: ignore
    return tuple(variants)


def _calculate_type_matric(type_: Any) -> int:
    if _is_concrete_type(type_):
        return 0

    priority = 0

    if _is_typealias(type_):
        for typevar in _get_typevars(type_):
            # for every typevar
            for _ in _get_typevar_variants(typevar):
                priority += 5
    else:
        for _ in _get_generics(type_):
            priority += 1000

    return priority


def _forward_ref(s: str) -> ForwardRef:
    return ForwardRef(s)


def _evaluate_forward_ref(fr: ForwardRef, module: ModuleType) -> Any | None:
    return fr._evaluate(module.__dict__, {}, frozenset())


class _Provider:
    def __init__(self, callable: Callable[..., Any], metric: int) -> None:
        self._callable = callable
        self._metric = metric

    @property
    def metric(self) -> int:
        return self._metric

    def __str__(self) -> str:
        return f"Provider[{self._callable.__name__} | {self._metric}]"

    def __repr__(self) -> str:
        return f"_Provider(callable={self._callable!r}, priority={self._metric!r})"


class _TypeNode:
    def __init__(self) -> None:
        self._provider: _Provider | None = None
        self._implementors: list[Any] = []

    @property
    def implementors(self) -> tuple[Any, ...]:
        return tuple(self._implementors)

    @property
    def provider(self) -> _Provider | None:
        return self._provider

    def set_provider(self, provider: _Provider) -> None:
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


class Scope:
    def __init__(self, name: str | None = None) -> None:
        self._name = name
        self._instances = {}

    def get_instance(self, type_: type[Any]) -> Any:
        if get_origin(type_) is Annotated:
            anno_type, *_ = get_args(type_)

            if _is_fixture_annotation(anno_type):
                return self._get_fixture(anno_type)
            else:
                return self._get_factory(anno_type)
        return self._get_factory(type_)

    def _get_factory(self, type_: type[Any]) -> None:
        pass

    def _get_fixture(self, type_: type[Any]) -> Any:
        pass


class Container:
    def __init__(self) -> None:
        # create a mapping between a type to the typenode, the key
        # types will always be concrete types and never expect typevar
        # if given type has typevars that are not bounded they will be replaced with `Any`
        self._entries: dict[type[Any], _TypeNode] = defaultdict(_TypeNode)
        self._forward_refs: dict[ModuleType, list[tuple[ForwardRef, _Provider]]] = (
            defaultdict(list)
        )
        self._lock = threading.Lock()

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
                evaluated = _evaluate_forward_ref(fr, module)
                self._add_provider(evaluated, provider)
            del self._forward_refs[module]

    def get_provider(self, type_: type[Any]) -> _Provider | None:
        if _is_typealias(type_) and _has_typevars(type_):
            # TODO
            # return self._get_generic_entry(type_)
            raise NotImplementedError

        if type_ in self._entries:
            return self._entries[type_].provider
        return None

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
        provider = _Provider(callable=callable, metric=_calculate_type_matric(type_))

        with self._lock:
            self._add_provider(type_, provider)

    def _add_provider(self, type_: Any, provider: _Provider) -> None:
        if isinstance(type_, str):
            module = cast(ModuleType, inspect.getmodule(callable))
            self._forward_refs[module].append((_forward_ref(type_), provider))
        elif isinstance(type_, TypeVar):
            if (variants := _unwrap_type(type_)) == (Any,):
                raise TypeError(
                    f"given typevar `{type_}` for provider `{callable.__name__}` is not bounded or constraint"
                )
            for variant in variants:
                self._add_entry(variant).set_provider(provider)
        elif not _is_concrete_type(type_):
            for variant in _all_typealias_variants(type_):
                self._add_provider(variant, provider)
        elif _is_typealias(type_):
            for tt in _unwrap_type(type_):
                if not _is_concrete_type(tt):
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
            g.__name__: v for g, v in zip(_get_generics(origin), get_args(type_))
        }

        # remember the orig base parents `origin` so we won't iterate
        # over them when we iter our `__mro__`
        orig_base_parents = []

        for orig_base in getattr(origin, "__orig_bases__", ()):
            if not _is_typealias(orig_base) or get_origin(orig_base) is Generic:
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
    def inject(self, __o: None = None, /) -> Callable[[_I], _I]: ...

    @overload
    def inject(self, __o: _I, /) -> _I: ...

    def inject(self, __o: _I | None = None, /) -> _I | Callable[[_I], _I]:
        def __inject(__o: _I, /) -> _I:
            if inspect.isclass(__o):
                self.add_provider(__o, __o.__init__)
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
                    try:
                        fr = _forward_ref(rt)
                        rt = _evaluate_forward_ref(fr, module)
                    except NameError:
                        # if the return type is a forward reference, we might be able to evaluate
                        # it at the spot, if not at leaset we tried
                        pass

                self.add_provider(rt, __o)
            return __o

        if __o is None:
            return __inject
        return __inject(__o)


defaultc = Container()
