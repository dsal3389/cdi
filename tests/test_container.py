import cdi
import pytest
from typing import Any
from ._common import Base, Foo, Parent, Child, MaleChild, provider_placehoder


@pytest.fixture
def ctr() -> cdi.Container:
    ctr = cdi.Container()
    ctr.add_provider(Foo, provider_placehoder)
    ctr.add_provider(Foo[str], provider_placehoder)
    ctr.add_provider(Foo[int], provider_placehoder)
    ctr.add_provider(Base, provider_placehoder)
    ctr.add_provider(MaleChild, provider_placehoder)
    return ctr


def test_expected_tree(ctr: cdi.Container) -> None:
    expected_typenodes: tuple[tuple[Any, tuple[Any, ...]], ...] = (
        (Foo[Any], ()),  # Foo
        (Foo[str], ()),  # Foo[str]
        (Foo[int], ()),  # Foo[int]
        (Base, (Parent[str],)),  # Base
        (Parent[str], (Child[str],)),  # MaleChild
        (Child[str], (MaleChild,)),  # MaleChild
        (MaleChild, ()),  # MaleChild
    )
    entries = ctr._entries  # type: ignore

    for type_, implementors in expected_typenodes:
        assert (
            type_ in entries
        ), f"couldn't find expected type `{type_.__name__}` in container entries"
        assert (
            entries[type_].implementors == implementors
        ), f"implementors mismatch for type `{type_.__name__}`"
