import os


class MonkSettings:
    """Global configuration settings for iron-monk."""

    defer: bool = True


settings = MonkSettings()

if os.environ.get("MONK_DEFER", "").strip().lower() in ("0", "false", "f", "no"):
    settings.defer = False
