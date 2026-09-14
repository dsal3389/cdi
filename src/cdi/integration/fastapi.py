import enum


class Lifetime(enum.Enum):
    APPLICATION = enum.auto()
    REQUEST = enum.auto()
