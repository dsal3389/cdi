# cdi
stands for "cute dependency injector" I guess(?)

## install
```sh
pip install cdi-di
```

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
@cdi.Injectable(ctr)
def get_int() -> int:
  return 100


# register `Foo` as injectable
# so we can create instances
@cdi.Injectable(ctr)
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
    

scope = cdi.Scope(__name__, container=ctr)
instance = scope.get_instance(MyType)
assert instance.field == "foo"
```

### what is not supported with generics (at least yet)
* TypeAliases as parameters are not supported (i.e `list[int]`)
* TypeAliases as injectable return type
* TypeVars as parameters
* Typevars as injectable return type


### Explicit is better then implicit
the library tries to make you explicit with your typing without compromising
readability or ease of use

# Documentation

## Container
container defines the scope of available types for injections, if you have
a `Scope` that want `int`, it will try to get the `int` factory from his container

thus you can have multiple `Containers` containing different types and provide separation
but most of the time you will be using a single global container

```py
ctr = cdi.Container()
```

### Inject factories
Containers contain is almost like a register of `Factories`, a factory can
be injected only through the `Injectable` class

## Forward references
some factories may have unresolved forward references in their return type or parameters, when evaluated
it is impossible to know what type sits behind those forward ref strings

```py
class Foo:
    # what is the `Boo` type? we just see a string
    def __init__(self, boo: 'Boo') -> None: ...
```

such factories will not be usable for injection, to resolve forward refs
the container class provide `update_forward_ref` which takes the module you want to update the forward refs for, this takes insperation
from `Pydantic/v1`

the `update_forward_ref` has to be called after there is a class that can evaluate the forward ref

```py
import sys

@cdi.Injectable(ctr)
class Foo:
    # references `Boo` which is not defined yet
    def __init__(self, boo: 'Boo') -> None: ...


@cdi.Injectable(ctr)
class Boo: ...


# now that `Boo` is defined, we can update the factories
# in our current module
ctr.update_forward_ref(sys.modules[__name__])

# works fine
instance = Scope(__name__, container=ctr).get_instance(Foo)
```

## Injectable
injectable is a type that creates factories based on the given type and registers
them with the given container

```py
ctr = cdi.Container()
injector = cdi.Injectable(ctr)

injector.register(Foo)
injector.register(my_func)
```

it can also be used as a decorator

```py
ctr = cdi.Container()

@cdi.Injectable(ctr)
class Foo: ...

@cdi.Injectable(ctr)
def my_func() -> int: ...
```

when creating the factory, the injector relys on the provided type hints

### Classes
when registering a class, the dependencies are taken from the class `__init__` signature, and the factory
implementation (what is called to return the type) uses the class `__call__`

### Functions
on functions, the function signature will be used to determin the parameters and return types, calling the factory
will call the provided function at the end

### Constant
a constant can be injected into the container, the constant type will be the factory return type, and all scopes
that require this type will evaluate to the constant, acting as a "global variable" in a container
for example
```py
ctr = cdi.Container()
cdi.Injectable().register("hello world")

scope = cdi.Scope(__name__, container=ctr)
assert scope.get_instance(str) == "hello world"
```

## Scopes
scopes provide sepration of live instances, they use the containers to get the factory, and they call
the factory to create a live instance that will be injected

```py
ctr = cdi.Container()

# we inject the `Foo` class into the `ctr` container
@cdi.Injectable(ctr)
class Foo:
    def __init__(self, number: int) -> None:
        self.number = number

cdi.Injectable(ctr).register(100)

# we define an instance scope that has access to the injectable
# registered in `ctr`
scope = cdi.Scope(__name__, container=ctr)
instance = scope.get_instance(Foo)
instance2 = scope.get_instance(Foo)

# the `Foo` will be evaluated only once and be reused
# for future calls
assert instance is instance2
assert instance.number == 100

scope2 = Scope(__name__ + '2', container=ctr)
scope2_instance = scope.get_instance(Foo)

# a different scopes don't have access to each other instances 
# although they are using the same container
assert scope2_instance is not instance
```

### inheritance
scopes can inherit parent and child like inheritance, the parent has no access to the child
but the child does have access to the parent

there is no unique behavior for the child/parent scope when they aquire the relevant roles, this is mostly
for ease of use, the real inheritance comes into play via `InjectableMetadata`

## annotation Metadata
you can change some default behaviors of the injectable type but in a way that make
sense, meaning, if you annotate `str` you cannot return `int`

types annotated with a metdata class `InjectableMetadata` is able to control some default behavior
of the scope 

### provider_scope
accepts a `Callable[[Scope], Scope]`, this effect which scope will instantiate the annotated type
the returned scope will be used for the type instanciation

```py
ctr = cdi.Container()
ctr2 = cdi.Container()

cdi.Injctable(ctr).register("hello world")
cdi.Injctable(ctr2).register("what?")

scope = Scope(__name__, container=ctr)
scope2 = scope.fork()


@cdi.Injectable(ctr2)
class Foo:
    def __init__(
        self,
        value1: str,
        value2: Annotated[
            str, 
            cdi.InjectableMetadata(provider_scope=lambda scope: scope.parent)  # get the str from the parent scope
        ]
    ) -> None:
        self.value1 = value1
        self.value2 = value2


instance = scope2.get_instance(Foo)
assert instance.value1 == "what?"
assert instance.value2 == "hello world"
```
