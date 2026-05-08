import dataclasses
import functools
import inspect
from typing import (
    get_type_hints,
    get_origin,
    get_args,
    TypeVar,
    dataclass_transform,
    Callable,
    Any,
    overload,
    ParamSpec,
    cast,
)

from .operations import (
    validate,
    validate_arguments,
    validate_return,
    _extract_monk_metadata,  # pyright: ignore[reportPrivateUsage]
    _PRIMITIVE_TYPES,  # pyright: ignore[reportPrivateUsage]
)
from .config import settings
from .exceptions import UnvalidatedAccessError

_obj_ga = object.__getattribute__
_obj_sa = object.__setattr__

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
    """Convenience decorator for custom constraints.

    Creates a high-performance dataclass (frozen and slotted by default).
    Intercepts the validation method to safely inject and format custom error messages.

    Args:
        cls: The class to decorate.
        frozen (bool): Whether the resulting dataclass should be frozen. Defaults to True.
        slots (bool): Whether the resulting dataclass should use __slots__. Defaults to True.
        **kwargs: Additional keyword arguments passed to dataclasses.dataclass.

    Returns:
        The transformed constraint class.
    """
    kwargs["frozen"] = frozen
    kwargs["slots"] = slots

    def wrapper(c: type[T]) -> type[T]:
        # Intercept the validate method to swap the error message on failure.
        # Hot paths skip the wrapper by calling `_validate_inner` directly and
        # formatting messages on caught exceptions; this preserves direct-call
        # behavior (`instance.validate(value)`) while removing wrapper overhead
        # from per-item loops.
        orig_validate = getattr(c, "validate")

        @functools.wraps(orig_validate)
        def new_validate(self: Any, value: Any) -> None:
            try:
                orig_validate(self, value)
            except ValueError:
                custom_message = getattr(self, "message", None)
                if custom_message is not None:
                    ctx = {"value": value}
                    if dataclasses.is_dataclass(self):
                        for f in dataclasses.fields(self):
                            ctx[f.name] = getattr(self, f.name)
                    try:
                        formatted = custom_message.format(**ctx)
                    except Exception:
                        formatted = custom_message
                    raise ValueError(formatted) from None
                raise

        setattr(c, "validate", new_validate)
        new_cls = dataclasses.dataclass(**kwargs)(c)
        # Hot-path entry point: skip wrapper, format on demand at catch sites.
        setattr(new_cls, "_validate_inner", orig_validate)
        return new_cls

    return wrapper if cls is None else wrapper(cls)


@overload
def monk(obj: type[T]) -> type[T]: ...


@overload
def monk(*, defer: bool | None = None, **dataclass_kwargs: Any) -> Callable[[type[T]], type[T]]: ...


@overload
def monk(obj: Callable[P, R]) -> Callable[P, R]: ...


@dataclass_transform()
def monk(obj: Any = None, *, defer: bool | None = None, **dataclass_kwargs: Any) -> Any:
    """The primary decorator for iron-monk.

    Transforms a class into a validated, guarded dataclass, OR validates function arguments and return values.

    Args:
        obj: The class or function to decorate.
        defer (bool | None): Whether to defer validation until `validate()` is called. Defaults to the global setting.
        **dataclass_kwargs: Additional keyword arguments passed to dataclasses.dataclass when decorating a class.

    Returns:
        The wrapped class or function.

    Raises:
        TypeError: If the decorated object is neither a class nor a function.
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

        if orig_post_init is None:

            def __post_init__(self: Any, *args: Any, **kwargs: Any) -> None:
                should_defer = defer if defer is not None else settings.defer
                if not should_defer:
                    validate(self)
        else:

            def __post_init__(self: Any, *args: Any, **kwargs: Any) -> None:
                # Temporarily uncloak the instance so 3rd-party __post_init__ hooks
                # (like Strawberry's one_of validation) can safely read fields.
                _obj_sa(self, "__monk_safe__", True)
                orig_post_init(self, *args, **kwargs)

                should_defer = defer if defer is not None else settings.defer
                if not should_defer:
                    validate(self)
                else:
                    # Re-cloak it for deferred validation
                    _obj_sa(self, "__monk_safe__", False)

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

        # 2. Extract metadata from type hints once
        hints = get_type_hints(d_cls, include_extras=True)
        rules = _extract_monk_metadata(hints)  # pyright: ignore[reportPrivateUsage]

        # __monk_fields__ filters out primitive-typed no-rule fields. They have no
        # constraints AND can't host nested @monk objects, so validate() can skip them.
        fields_to_check: list[str] = []
        for f in dataclasses.fields(cast(Any, d_cls)):
            if f.name in rules:
                fields_to_check.append(f.name)
                continue
            hint = hints[f.name]
            base = hint
            if hasattr(hint, "__metadata__"):
                args = get_args(hint)
                if args:
                    base = args[0]
            origin = get_origin(base)
            if origin is None and isinstance(base, type) and base in _PRIMITIVE_TYPES:
                continue  # primitive scalar, nothing to validate or recurse into
            fields_to_check.append(f.name)

        setattr(d_cls, "__monk_fields__", tuple(fields_to_check))
        setattr(d_cls, "__monk_rules__", rules)
        # Skip per-instance hook lookups when the class doesn't define one.
        setattr(d_cls, "__monk_has_validate_hook__", any("__monk_validate__" in vars(b) for b in d_cls.__mro__))

        # Overwrite __getattribute__ to guard the dataclass until validated.
        # Hot path: validated access. Read __monk_safe__ first; if True, return attr immediately.
        def __getattribute__(self: Any, name: str) -> Any:
            if _obj_ga(self, "__monk_safe__"):
                return _obj_ga(self, name)
            if name == "validate" or name.startswith("_"):
                return _obj_ga(self, name)
            raise UnvalidatedAccessError(f"Monk Protection: Validate {self.__class__.__name__} before access.")

        setattr(d_cls, "__getattribute__", __getattribute__)

        # Patch __repr__ so printing an unvalidated object doesn't crash the app
        orig_repr = d_cls.__repr__

        def __repr__(self: Any) -> str:
            if not _obj_ga(self, "__monk_safe__"):
                return f"<{self.__class__.__name__} (Guarded/Unvalidated)>"
            return orig_repr(self)

        setattr(d_cls, "__repr__", __repr__)

        return d_cls

    def _wrap_function(func: Callable[P, R]) -> Callable[P, R]:
        hints = get_type_hints(func, include_extras=True)
        rules = _extract_monk_metadata(hints)
        return_constraints = rules.pop("return", None)
        sig = inspect.signature(func)

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                validate_arguments(bound.arguments, rules)
                result = await func(*args, **kwargs)
                if return_constraints is not None:
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
                if return_constraints is not None:
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
