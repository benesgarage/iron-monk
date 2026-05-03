import os
from typing import Any, Callable


class MonkSettings:
    """Global configuration settings for iron-monk."""

    defer: bool = True
    default_allow_none: bool = False
    unwrappers: dict[Any, Callable[[Any], Any]] = {}
    type_metadata: dict[Any, list[Any]] = {}

    def unwrap(self, val: Any) -> Any:
        if not self.unwrappers:
            return val
        unwrapper = self.unwrappers.get(type(val))
        if unwrapper is not None:
            return unwrapper(val)
        return val


settings = MonkSettings()

if os.environ.get("MONK_DEFER", "").strip().lower() in ("0", "false", "f", "no"):
    settings.defer = False
if os.environ.get("MONK_DEFAULT_ALLOW_NONE", "").strip().lower() in ("1", "true", "t", "yes"):
    settings.default_allow_none = True
