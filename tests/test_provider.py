import cdi
import pytest
from typing import Never
from ._common import Base, Foo, Complex, T, R


def x_provider() -> Never:
    raise NotImplementedError


def y_provider() -> Never:
    raise NotImplementedError


def z_provider() -> Never:
    raise NotImplementedError


@pytest.fixture
def ctr() -> cdi.Container:
    return cdi.Container()


# def test_concrete_priority(ctr: cdi.Container) -> None:
#     ctr.add_provider(Base, x_provider)
#     ctr.add_provider(Foo[R], y_provider)
#     ctr.add_provider(Foo[int], z_provider)
#
#     assert ctr.get_provider(Foo[int])._callable is z_provider
#     assert ctr.get_provider(Foo[str])._callable is y_provider
