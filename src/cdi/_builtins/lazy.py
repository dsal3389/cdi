import cdi
from typing import TypeVar, Generic, Annotated


_T = TypeVar("_T")


class Lazy(Generic[_T]):
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
        if self._instance is None:
            self._instance = self._scope.get_instance(self._type)
        return self._instance
