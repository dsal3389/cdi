# cdi
injector that supports generics

## generic resolution
before you use `cdi` to support generics, it is better to understand how `cdi` will try to resolve generics
to their concrete types

### internal representation
each container has internal map between a concerete type, to the provider (callable or none if there is no provider) and subtypes that implement
the type

when you add a provider for a type, `cdi` will take the type and create a new entry for your type and the type parents,
for example

```py
class Parent:
    pass


class Child:
    pass


ctr = cdi.Container()
ctr.add_provider(Child, provider)

# ctr internal mapping will look like so
# {
#   Parent: (None, (Child,)),
#   Child: (provider, ())
# }
```

notice that the parent also has an entry in the container mapping, this is the main power
for generic resolution

the internal mapping will always be concrete types and the container never holds generics in
its mapping, so what if you have a type that accept generic?

simply `cdi` will try to resolve this generics based on its `bounds` or `coveriants`, if the generic
is not bounded to those, it will be treated as `Any`

```py
T = TypeVar("T")


class Wrapper(Generic[T]):
    pass


class Base:
    pass


B = TypeVar("B", bound=Base)


class BaseWrapper(Generic[B]):
    pass


ctr = cdi.Container()
ctr.add_provider(Wrapper[T], wrapper_provider)
ctr.add_provider(Basewrapper, base_provider)  # we can omit the generics

# internal representation
# {
#   Wrapper[Any]: (wrapper_provider, ()),
#   BaseWrapper[Base]: (base_provider, ()),
# }
```

---
