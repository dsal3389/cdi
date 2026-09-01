import cdi
from typing import TypeVar, Generic, Annotated


_T = TypeVar("_T")


class Lazy(Generic[_T]):
    """
    the lazy type is a builtin generic type that can be used in
    cases of circular dependency

    ```py
    @cdi.Injectable(ctr)
    class A:
        def __init__(self, b: B) -> None: ...

    @cdi.Injectable(ctr)
    class B:
        def __init__(self, a: A) -> None: ...

    ctr.update_forward_refs(sys.modules[__name__])

    scope = cdi.Scope(ctr)
    scope.get_instance(A)  # error due to circular dep
    ```

    lazy solves the issue by making one of the dependencies a lazy
    object
    ```py
    @cdi.Injectable(ctr)
    class A:
        def __init__(self, b: B) -> None: ...

    @cdi.Injectable(ctr)
    class B:
        def __init__(self, a: cdi.Lazy[A]) -> None: ...

    ctr.update_forward_refs(sys.modules[__name__])

    scope = cdi.Scope(ctr)
    instance = scope.get_instance(A)  # ok
    assert instance.b.a.wake() is instance
    ```

    ## activating Lazy
    currently lazy is not activated by default, to use lazy in your injection
    you need to do 2 things

    1. register `Lazy` factory in the container level
    ```py
    cdi.Injectable(ctr).register(cdi.Lazy)
    ```
    2. insert the scope instance as injectable
    ```py
    scope.insert_instance(scope)
    ```
    """

    def __init__(
        self,
        type_: type[_T],
        scope: Annotated[
            cdi.Scope,
            cdi.InjectableMetadata(
                error_message="to use `Lazy` it is required to insert the `Scope` instance"
            )
        ]
    ) -> None:
        self._type = type_
        self._scope = scope
        self._instance: _T | None = None

    def wake(self) -> _T:
        """wakes up the lazy type for instance evaluation"""
        if self._instance is None:
            self._instance = self._scope.get_instance(self._type)
        return self._instance
