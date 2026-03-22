# App Configuration

Pair explicit environment variable extraction with fail-fast validation for a robust, crash-early application boot sequence.

```python
import os
from typing import Annotated
from monk import monk
from monk.constraints import URL, OneOf, Interval
from monk.exceptions import ValidationError

# Use defer=False to instantly crash on boot if misconfigured
@monk(defer=False)
class AppConfig:
    environment: Annotated[str, OneOf(["development", "staging", "production"])]
    database_url: Annotated[str, URL]
    port: Annotated[int, Interval(ge=1024, le=65535)]

def load_config() -> AppConfig:
    return AppConfig(
        environment=os.environ.get("ENV", "development"),
        database_url=os.environ.get("DATABASE_URL", "postgres://localhost:5432/db"),
        port=int(os.environ.get("PORT", "8000")),
    )

# Simulating a bad deployment config
os.environ["ENV"] = "testing" 
os.environ["PORT"] = "80" 

try:
    config = load_config()
except ValidationError as e:
    print("CRITICAL: App failed to boot:")
    print("\n".join(e.flatten()))
```

### Output
```bash
CRITICAL: App failed to boot:
environment: Must be one of: ['development', 'staging', 'production'], got 'testing'.
port: Must be greater than or equal to 1024.
```