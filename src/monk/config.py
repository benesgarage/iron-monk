import os


class MonkSettings:
    """Global configuration settings for iron-monk."""
    deferred_validation: bool = True

settings = MonkSettings()

if os.environ.get("MONK_DEFERRED_VALIDATION", "").strip().lower() in ("0", "false", "f", "no"):
    settings.deferred_validation = False