import dataclasses
import functools
import inspect
from typing import (
    get_type_hints,
    TypeVar,
    dataclass_transform,
    Callable,
    Any,
    overload,
    ParamSpec,
    cast,
)

from .operations import validate, validate_arguments, validate_return, _extract_monk_metadata  # pyright: ignore[reportPrivateUsage]
from .config import settings
from .exceptions import UnvalidatedAccessError

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


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

    def wrapper(c: type[T]) -> type[T]:
        # Intercept the validate method to swap the error message on failure
        orig_validate = getattr(c, "validate")

        @functools.wraps(orig_validate)
        def new_validate(self: Any, value: Any) -> None:
            try:
                orig_validate(self, value)
            except ValueError:
                custom_message = getattr(self, "message", None)
                if custom_message is not None:
                    # Safely build formatting context without deep-copying (to avoid crashes on regex/unpicklable objects)
                    ctx = {"value": value}
                    if dataclasses.is_dataclass(self):
                        for f in dataclasses.fields(self):
                            ctx[f.name] = getattr(self, f.name)
                    try:
                        formatted = custom_message.format(**ctx)
                    except Exception:
                        formatted = custom_message  # Fallback if string formatting fails
                    raise ValueError(formatted) from None
                raise

        setattr(c, "validate", new_validate)
        return dataclasses.dataclass(**kwargs)(c)

    return wrapper if cls is None else wrapper(cls)


@overload
def monk(obj: type[T]) -> type[T]: ...


@overload
def monk(*, defer: bool | None = None, **dataclass_kwargs: Any) -> Callable[[type[T]], type[T]]: ...


@overload
def monk(obj: Callable[P, R]) -> Callable[P, R]: ...


@dataclass_transform()
def monk(obj: Any = None, *, defer: bool | None = None, **dataclass_kwargs: Any) -> Any:
    """
    The primary decorator for iron-monk.
    Transforms a class into a validated, guarded dataclass, OR validates function arguments.
    """

    def _wrap_class(original_cls: type[T]) -> type[T]:
        # Safely get class annotations (handles Python 3.14+ lazy evaluation)
        ann = dict(inspect.get_annotations(original_cls))
        ann["__monk_safe__"] = bool
        original_cls.__annotations__ = ann

        setattr(
            original_cls,
            "__monk_safe__",
            dataclasses.field(default=False, init=False, repr=False, compare=False, hash=False),
        )

        orig_post_init = getattr(original_cls, "__post_init__", None)

        def __post_init__(self: Any, *args: Any, **kwargs: Any) -> None:
            if orig_post_init is not None:
                orig_post_init(self, *args, **kwargs)

            # Explicit kwarg overrides global config
            should_defer = defer if defer is not None else settings.defer
            if not should_defer:
                validate(self)

        setattr(original_cls, "__post_init__", __post_init__)

        # 1. Convert to a standard dataclass
        d_cls = dataclasses.dataclass(original_cls, **dataclass_kwargs)

        # Hide our internal tracking field from external libraries (like Strawberry or FastAPI)
        # so they don't expose it in GraphQL/OpenAPI schemas or try to instantiate it.
        if hasattr(d_cls, "__annotations__"):
            d_cls.__annotations__.pop("__monk_safe__", None)

        dataclass_fields = getattr(d_cls, "__dataclass_fields__", None)
        if dataclass_fields is not None:
            dataclass_fields.pop("__monk_safe__", None)

        fields_tuple = tuple(f.name for f in dataclasses.fields(cast(Any, d_cls)))
        setattr(d_cls, "__monk_fields__", fields_tuple)

        # 2. Extract metadata from type hints once
        hints = get_type_hints(d_cls, include_extras=True)
        rules = _extract_monk_metadata(hints)  # pyright: ignore[reportPrivateUsage]

        setattr(d_cls, "__monk_rules__", rules)

        # Overwrite __getattribute__ to guard the dataclass until validated
        def __getattribute__(self: Any, name: str) -> Any:
            if name == "validate" or name.startswith("_"):
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

    def _wrap_function(func: Callable[P, R]) -> Callable[P, R]:
        hints = get_type_hints(func, include_extras=True)
        rules = _extract_monk_metadata(hints)
        return_constraints = rules.pop("return", [])
        sig = inspect.signature(func)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                validate_arguments(bound.arguments, rules)
                result = await func(*args, **kwargs)
                if return_constraints:
                    validate_return(result, return_constraints)
                return result

            return cast(Callable[P, R], async_wrapper)
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                validate_arguments(bound.arguments, rules)
                result = func(*args, **kwargs)
                if return_constraints:
                    validate_return(result, return_constraints)
                return result

            return sync_wrapper

    def router(target: Any) -> Any:
        if inspect.isclass(target):
            return _wrap_class(target)
        elif inspect.isroutine(target):
            return _wrap_function(target)
        raise TypeError("Monk can only decorate classes or functions.")

    return router if obj is None else router(obj)
