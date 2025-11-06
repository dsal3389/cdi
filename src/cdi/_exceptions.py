__all__ = ("CdiException", "MissingAnnotation")


class CdiException(Exception):
    pass


class MissingAnnotation(CdiException):
    pass
