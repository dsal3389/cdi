# cdi
stands for "cute dependency injector" I guess?


## Dependency injection made easy
while some python dependency injectors require some setup and make some things
harder to understand for a simple dependency injection, `cdi` aims to simplify
dependency injection and be fast (relativly to python)

```py
import cdi

# this container will contain its own registered types
ctr = cdi.Container()


# register this function as a factory
# for the `int` type
@cdi.Injectable(ctr=ctr)
def get_int() -> int:
  return 100


# register `Foo` as injectable
# so we can create instances
@cdi.Injectable(ctr=ctr)
class Foo:
  def __init__(self, number: int) -> None:
      self.number = number


# create a scope that will have access to registered
# types in `ctr` then get an instance of `Foo`
scope = cdi.Scope(cdi)
instance = scope.get_instance(Foo)
assert instance.number == 100
```

## Support Generics

```py
import cdi 
from typing import Generic, TypeVar
from collection.abc import Sequence


T = TypeVar('T')

ctr = cdi.Container()


class MyBase(Generic[T]):
    def __init__(self, field: T) -> None:
        self.field = field


@cdi.Injectable(ctr)
class MyType(MyBase[str]):
    pass


@cdi.Injectable(ctr)
def name_generator() -> str:
    return "foo"
    

scope = cdi.Scope(ctr)
instance = scope.get_instance(MyType)
assert instance.field == "foo"
```

### what is not supported with generics (at least yet)
* TypeAliases as parameters are not supported (i.e `list[int]`)
* TypeAliases as injectable return type
* TypeVars as parameters
* Typevars as injectable return type
