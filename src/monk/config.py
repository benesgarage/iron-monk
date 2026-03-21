import os


class MonkSettings:
    """Global configuration settings for iron-monk."""

    defer: bool = True
    default_allow_none: bool = False


settings = MonkSettings()

if os.environ.get("MONK_DEFER", "").strip().lower() in ("0", "false", "f", "no"):
    settings.defer = False
if os.environ.get("MONK_DEFAULT_ALLOW_NONE", "").strip().lower() in ("1", "true", "t", "yes"):
    settings.default_allow_none = True
