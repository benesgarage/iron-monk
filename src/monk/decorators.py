import dataclasses
import functools
import inspect
from typing import get_type_hints, TypeVar, dataclass_transform, Callable, Any, overload
from .protocols import MonkConstraint
from .operations import validate
from .config import settings
from .exceptions import UnvalidatedAccessError

T = TypeVar("T")


@overload
def constraint(cls: type[T]) -> type[T]: ...


@overload
def constraint(*, frozen: bool = True, slots: bool = True, **kwargs: Any) -> Callable[[type[T]], type[T]]: ...


@dataclass_transform(frozen_default=True)
def constraint(
    cls: type[T] | None = None, *, frozen: bool = True, slots: bool = True, **kwargs: Any
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Convenience decorator for custom constraints.
    Creates a high-performance dataclass (frozen and slotted by default).
    """
    kwargs["frozen"] = frozen
    kwargs["slots"] = slots
    if cls is None:

        def wrapper(c: type[T]) -> type[T]:
            return dataclasses.dataclass(**kwargs)(c)

        return wrapper
    return dataclasses.dataclass(**kwargs)(cls)


@overload
def monk(cls: type[T]) -> type[T]: ...


@overload
def monk(*, deferred_validation: bool | None = None, **dataclass_kwargs: Any) -> Callable[[type[T]], type[T]]: ...


@dataclass_transform()
def monk(
    cls: type[T] | None = None, *, deferred_validation: bool | None = None, **dataclass_kwargs: Any
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    The primary decorator for iron-monk.
    Transforms a class into a validated, guarded dataclass.
    """

    def wrap(original_cls: type[T]) -> type[T]:
        # Safely get class annotations (handles Python 3.14+ lazy evaluation)
        ann = dict(inspect.get_annotations(original_cls))
        ann["__monk_safe__"] = bool
        original_cls.__annotations__ = ann

        setattr(
            original_cls,
            "__monk_safe__",
            dataclasses.field(default=False, init=False, repr=False, compare=False, hash=False),
        )

        # 1. Convert to a standard dataclass
        d_cls = dataclasses.dataclass(original_cls, **dataclass_kwargs)

        # Hide our internal tracking field from external libraries (like Strawberry or FastAPI)
        # so they don't expose it in GraphQL/OpenAPI schemas or try to instantiate it.
        if hasattr(d_cls, "__annotations__"):
            d_cls.__annotations__.pop("__monk_safe__", None)

        dataclass_fields = getattr(d_cls, "__dataclass_fields__", None)
        if dataclass_fields is not None:
            dataclass_fields.pop("__monk_safe__", None)

        # 2. Extract metadata from type hints once
        hints = get_type_hints(d_cls, include_extras=True)
        rules = {}
        for name, hint in hints.items():
            # Look for our specific MonkConstraint in Annotated metadata
            metadata = getattr(hint, "__metadata__", [])
            field_rules = []
            for m in metadata:
                # Auto-instantiate classes that implement the protocol but were passed as a type
                if isinstance(m, type) and issubclass(m, MonkConstraint):
                    try:
                        field_rules.append(m())
                    except TypeError as e:
                        raise TypeError(
                            f"Constraint '{m.__name__}' missing required arguments. Did you mean {m.__name__}(...)?"
                        ) from e
                elif isinstance(m, MonkConstraint):
                    field_rules.append(m)

            if field_rules:
                rules[name] = field_rules

        setattr(d_cls, "__monk_rules__", rules)

        # Ensure every new instance starts in a guarded/unvalidated state
        orig_init = d_cls.__init__

        @functools.wraps(orig_init)
        def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
            kwargs.pop("__monk_safe__", None)  # Shield against aggressive external instantiators
            object.__setattr__(self, "__monk_safe__", False)
            orig_init(self, *args, **kwargs)

            # Explicit kwarg overrides global config
            should_defer = deferred_validation if deferred_validation is not None else settings.deferred_validation
            if not should_defer:
                validate(self)

        setattr(d_cls, "__init__", __init__)

        # Overwrite __getattribute__ to guard the dataclass until validated
        def __getattribute__(self: Any, name: str) -> Any:
            if name in ("__monk_safe__", "validate") or name.startswith("__"):
                return object.__getattribute__(self, name)

            if not object.__getattribute__(self, "__monk_safe__"):
                raise UnvalidatedAccessError(f"Monk Protection: Validate {self.__class__.__name__} before access.")

            return object.__getattribute__(self, name)

        setattr(d_cls, "__getattribute__", __getattribute__)

        # Patch __repr__ so printing an unvalidated object doesn't crash the app
        orig_repr = d_cls.__repr__

        def __repr__(self: Any) -> str:
            if not object.__getattribute__(self, "__monk_safe__"):
                return f"<{self.__class__.__name__} (Guarded/Unvalidated)>"
            return orig_repr(self)

        setattr(d_cls, "__repr__", __repr__)

        return d_cls

    return wrap if cls is None else wrap(cls)
