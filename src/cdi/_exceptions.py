__all__ = ("CdiException", "MissingAnnotation", "NoProviderForType")


class CdiException(Exception):
    pass


class MissingAnnotation(CdiException):
    pass


class NoProviderForType(CdiException):
    pass
