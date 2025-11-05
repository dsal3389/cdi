import cdi
import pytest
from typing import Any, TypeVar, Generic
from ._common import Base, Foo, provider_placehoder


@pytest.fixture
def ctr() -> cdi.Container:
    return cdi.Container()


def _assert_entries(
    expected_typenodes: tuple[tuple[Any, tuple[Any, ...]], ...], entries: dict[Any, Any]
):
    for type_, implementors in expected_typenodes:
        assert (
            type_ in entries
        ), f"couldn't find expected type `{type_.__name__}` in container entries"
        assert (
            entries[type_].implementors == implementors
        ), f"implementors mismatch for type `{type_.__name__}`"

    assert len(expected_typenodes) == len(entries)


def test_with_custom_types(ctr: cdi.Container) -> None:
    T = TypeVar("T")

    class Parent(Base, Generic[T]):
        pass

    class Child(Generic[T], Parent[T]):
        pass

    class MaleChild(Child[str]):
        pass

    ctr.add_provider(Foo, provider_placehoder)
    ctr.add_provider(Foo[str], provider_placehoder)
    ctr.add_provider(Foo[int], provider_placehoder)
    ctr.add_provider(Base, provider_placehoder)
    ctr.add_provider(MaleChild, provider_placehoder)
    _assert_entries(
        (
            (Foo[Any], ()),  # Foo
            (Foo[str], ()),  # Foo[str]
            (Foo[int], ()),  # Foo[int]
            (Base, (Parent[str],)),  # Base
            (Parent[str], (Child[str],)),  # MaleChild
            (Child[str], (MaleChild,)),  # MaleChild
            (MaleChild, ()),  # MaleChild
        ),
        ctr._entries,
    )


def test_union_tree(ctr: cdi.Container) -> None:
    ctr.add_provider(int | str, provider_placehoder)
    ctr.add_provider(list[str] | list[int], provider_placehoder)
    _assert_entries(
        (
            (int, ()),
            (str, ()),
            (list[str], ()),
            (list[int], ()),
        ),
        ctr._entries,
    )


def test_typevars(ctr: cdi.Container) -> None:
    I = TypeVar("I", int, str)
    B = TypeVar("R", bound=Base)

    class Foo(Base):
        pass

    ctr.add_provider(I, provider_placehoder)
    ctr.add_provider(B, provider_placehoder)
    ctr.add_provider(Foo, provider_placehoder)
    _assert_entries(((int, ()), (str, ()), (Base, (Foo,)), (Foo, ())), ctr._entries)


def test_invalid_types(ctr: cdi.Container) -> None:
    T = TypeVar("T")

    with pytest.raises(TypeError):
        ctr.add_provider(T, provider_placehoder)
