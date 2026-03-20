import os
from typing import Annotated

from monk import monk
from monk.constraints import URL, OneOf, Interval
from monk.exceptions import ValidationError


# 1. Define your Configuration Schema
# We use defer=False so the app instantly crashes on boot
# if the environment variables are misconfigured!
@monk(defer=False)
class AppConfig:
    environment: Annotated[str, OneOf(["development", "staging", "production"])]
    database_url: Annotated[str, URL]
    # 1024-65535 is the standard range for unprivileged ports
    port: Annotated[int, Interval(ge=1024, le=65535)]


# 2. Load from environment variables
def load_config() -> AppConfig:
    return AppConfig(
        environment=os.environ.get("ENV", "development"),
        database_url=os.environ.get("DATABASE_URL", "postgres://user:pass@localhost:5432/db"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    # --- 🟢 Success Path ---
    config = load_config()
    print(f"App booting in {config.environment} on port {config.port}...")

    # --- 🔴 Failure Path (Simulating a bad deployment) ---
    print("\nSimulating a bad deployment config...")
    os.environ["ENV"] = "testing"  # Not in our allowed OneOf list!
    os.environ["PORT"] = "80"  # Privileged port!

    try:
        bad_config = load_config()
    except ValidationError as e:
        print("CRITICAL: Application failed to boot due to configuration errors:")
        for err in e.errors:
            print(f" - {err['field']}: {err['message']}")
