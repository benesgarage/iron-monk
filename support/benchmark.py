import timeit
import sys
import subprocess

print("Running Benchmarks... (This may take a few seconds)\n")


# ---------------------------------------------------------
# 1. Cold Start (Import Time via Subprocess)
# ---------------------------------------------------------
def measure_import(package: str) -> float:
    code = f"import {package}"
    cmd = [sys.executable, "-c", code]
    times = []
    for _ in range(5):
        start = timeit.default_timer()
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        times.append(timeit.default_timer() - start)
    return min(times)


def measure_size(*packages: str) -> str:
    code = """
import os, importlib.util, sys
total = 0
for pkg in sys.argv[1:]:
    spec = importlib.util.find_spec(pkg)
    if spec:
        if spec.submodule_search_locations:
            for path in spec.submodule_search_locations:
                for dirpath, dirnames, filenames in os.walk(path):
                    if "__pycache__" in dirnames:
                        dirnames.remove("__pycache__")
                    for f in filenames:
                        if f.endswith(('.pyc', '.pyo')):
                            continue
                        fp = os.path.join(dirpath, f)
                        if not os.path.islink(fp):
                            total += os.path.getsize(fp)
        elif spec.origin:
            total += os.path.getsize(spec.origin)
print(total)
"""
    cmd = [sys.executable, "-c", code] + list(packages)
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        mb = int(res.stdout.strip()) / (1024 * 1024)
        return f"{mb:.2f} MB" if mb >= 0.01 else "<0.01 MB"
    except Exception:
        return "N/A"


monk_import = measure_import("monk")
pydantic_import = measure_import("pydantic")
msgspec_import = measure_import("msgspec")
attrs_import = measure_import("attrs")
marshmallow_import = measure_import("marshmallow")
voluptuous_import = measure_import("voluptuous")

monk_size = measure_size("monk")
pydantic_size = measure_size("pydantic", "pydantic_core", "annotated_types")
msgspec_size = measure_size("msgspec")
attrs_size = measure_size("attrs", "attr")
marshmallow_size = measure_size("marshmallow")
voluptuous_size = measure_size("voluptuous")

# ---------------------------------------------------------
# 2. Object Instantiation & Validation (Fail-Fast)
# ---------------------------------------------------------
setup_monk = """
from typing import Annotated
from monk import monk
from monk.constraints import Len, Interval

@monk(defer=False)
class User:
    id: int
    username: Annotated[str, Len(min_len=3)]
    age: Annotated[int, Interval(ge=18)]
"""
run_monk = 'User(id=1, username="kai", age=25)'

setup_pydantic = """
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    username: str = Field(min_length=3)
    age: int = Field(ge=18)
"""
run_pydantic = 'User(id=1, username="kai", age=25)'

setup_attrs = """
from attrs import define, field, validators

@define
class User:
    id: int = field(validator=validators.instance_of(int))
    username: str = field(validator=[validators.instance_of(str), validators.min_len(3)])
    age: int = field(validator=[validators.instance_of(int), validators.ge(18)])
"""
run_attrs = 'User(id=1, username="kai", age=25)'

setup_msgspec_obj = """
import msgspec
from typing import Annotated

class User(msgspec.Struct):
    id: int
    username: Annotated[str, msgspec.Meta(min_length=3)]
    age: Annotated[int, msgspec.Meta(ge=18)]

data = {"id": 1, "username": "kai", "age": 25}
"""
run_msgspec_obj = "msgspec.convert(data, User)"

# ---------------------------------------------------------
# 3. Raw Dictionary Validation
# ---------------------------------------------------------
setup_monk_dict = """
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Len, Interval

class UserDict(TypedDict):
    id: int
    username: Annotated[str, Len(min_len=3)]
    age: Annotated[int, Interval(ge=18)]
    
data = {"id": 1, "username": "kai", "age": 25}
bad_data = {"id": "bad", "username": "a", "age": 10}
messy_data = {"id": 1, "username": "kai", "age": 25, "tracking_id": "123", "is_admin": True, "browser": "chrome"}
"""
run_monk_dict = "validate_dict(data, UserDict)"

# Sanitization Validation (Dropping extra keys)
run_monk_sanitized = "validate_dict(messy_data, UserDict, drop_extra_keys=True)"

# Partial Validation (PATCH) - Only passing age
run_monk_partial = 'validate_dict({"age": 25}, UserDict, partial=True)'

run_monk_invalid = """try:
    validate_dict(bad_data, UserDict)
except Exception:
    pass
"""

setup_pydantic_dict = """
from pydantic import BaseModel, Field, TypeAdapter

class User(BaseModel):
    id: int
    username: str = Field(min_length=3)
    age: int = Field(ge=18)
    
adapter = TypeAdapter(User)
data = {"id": 1, "username": "kai", "age": 25}
bad_data = {"id": "bad", "username": "a", "age": 10}
messy_data = {"id": 1, "username": "kai", "age": 25, "tracking_id": "123", "is_admin": True, "browser": "chrome"}
"""
run_pydantic_dict = "adapter.validate_python(data)"

# Pydantic ignores extra keys by default
run_pydantic_sanitized = "adapter.validate_python(messy_data)"

run_pydantic_invalid = """try:
    adapter.validate_python(bad_data)
except Exception:
    pass
"""

setup_msgspec_dict = """
import msgspec
from typing import TypedDict, Annotated

class UserDict(TypedDict):
    id: int
    username: Annotated[str, msgspec.Meta(min_length=3)]
    age: Annotated[int, msgspec.Meta(ge=18)]

data = {"id": 1, "username": "kai", "age": 25}
bad_data = {"id": "bad", "username": "a", "age": 10}
messy_data = {"id": 1, "username": "kai", "age": 25, "tracking_id": "123", "is_admin": True, "browser": "chrome"}
"""
run_msgspec_dict = "msgspec.convert(data, UserDict)"

# Msgspec ignores extra keys by default on TypedDicts
run_msgspec_sanitized = "msgspec.convert(messy_data, UserDict)"

run_msgspec_invalid = """try:
    msgspec.convert(bad_data, UserDict)
except Exception:
    pass
"""

setup_marshmallow = """
from marshmallow import Schema, fields, validate, EXCLUDE

class UserSchema(Schema):
    id = fields.Int(required=True)
    username = fields.Str(validate=validate.Length(min=3), required=True)
    age = fields.Int(validate=validate.Range(min=18), required=True)
    
schema = UserSchema(unknown=EXCLUDE)
data = {"id": 1, "username": "kai", "age": 25}
bad_data = {"id": "bad", "username": "a", "age": 10}
messy_data = {"id": 1, "username": "kai", "age": 25, "tracking_id": "123", "is_admin": True, "browser": "chrome"}
"""
run_marshmallow = "schema.load(data)"

# Sanitization Validation
run_marshmallow_sanitized = "schema.load(messy_data)"

# Partial Validation (PATCH) - Only passing age
run_marshmallow_partial = 'schema.load({"age": 25}, partial=True)'

run_marshmallow_invalid = """try:
    schema.load(bad_data)
except Exception:
    pass
"""

setup_voluptuous = """
from voluptuous import Schema, Required, Length, All, Range, REMOVE_EXTRA

schema = Schema({
    Required('id'): int,
    Required('username'): All(str, Length(min=3)),
    Required('age'): All(int, Range(min=18)),
}, extra=REMOVE_EXTRA)
data = {"id": 1, "username": "kai", "age": 25}
bad_data = {"id": "bad", "username": "a", "age": 10}
messy_data = {"id": 1, "username": "kai", "age": 25, "tracking_id": "123", "is_admin": True, "browser": "chrome"}
"""
run_voluptuous = "schema(data)"

# Sanitization Validation
run_voluptuous_sanitized = "schema(messy_data)"

run_voluptuous_invalid = """try:
    schema(bad_data)
except Exception:
    pass
"""

# ---------------------------------------------------------
# 4. Nested Dictionary Validation
# ---------------------------------------------------------
setup_monk_nested = """
from typing import TypedDict, Annotated
from monk import validate_dict
from monk.constraints import Len, Nested, Each

class AddressDict(TypedDict):
    city: Annotated[str, Len(min_len=2)]

class UserDict(TypedDict):
    id: int
    address: Annotated[AddressDict, Nested(AddressDict)]
    history: Annotated[list[AddressDict], Each(Nested(AddressDict))]

data = {
    "id": 1,
    "address": {"city": "New York"},
    "history": [{"city": "London"}, {"city": "Paris"}]
}
"""
run_monk_nested = "validate_dict(data, UserDict)"

setup_pydantic_nested = """
from pydantic import BaseModel, Field, TypeAdapter

class Address(BaseModel):
    city: str = Field(min_length=2)

class User(BaseModel):
    id: int
    address: Address
    history: list[Address]

adapter = TypeAdapter(User)
data = {
    "id": 1,
    "address": {"city": "New York"},
    "history": [{"city": "London"}, {"city": "Paris"}]
}
"""
run_pydantic_nested = "adapter.validate_python(data)"

setup_msgspec_nested = """
import msgspec
from typing import Annotated

class Address(msgspec.Struct):
    city: Annotated[str, msgspec.Meta(min_length=2)]

class User(msgspec.Struct):
    id: int
    address: Address
    history: list[Address]

data = {
    "id": 1,
    "address": {"city": "New York"},
    "history": [{"city": "London"}, {"city": "Paris"}]
}
"""
run_msgspec_nested = "msgspec.convert(data, User)"

# ---------------------------------------------------------
# 5. Function Validation
# ---------------------------------------------------------
setup_monk_func = """
from typing import Annotated
from monk import monk
from monk.constraints import Len

@monk
def process(username: Annotated[str, Len(min_len=3)]):
    pass
"""
run_monk_func = 'process(username="kai")'

setup_pydantic_func = """
from pydantic import validate_call, Field

@validate_call
def process(username: str = Field(min_length=3)):
    pass
"""
run_pydantic_func = 'process(username="kai")'

# ---------------------------------------------------------
# Execute
# ---------------------------------------------------------
ITERATIONS = 100_000

monk_obj_time = timeit.timeit(run_monk, setup=setup_monk, number=ITERATIONS)
pydantic_obj_time = timeit.timeit(run_pydantic, setup=setup_pydantic, number=ITERATIONS)
msgspec_obj_time = timeit.timeit(run_msgspec_obj, setup=setup_msgspec_obj, number=ITERATIONS)
attrs_obj_time = timeit.timeit(run_attrs, setup=setup_attrs, number=ITERATIONS)

monk_dict_time = timeit.timeit(run_monk_dict, setup=setup_monk_dict, number=ITERATIONS)
pydantic_dict_time = timeit.timeit(run_pydantic_dict, setup=setup_pydantic_dict, number=ITERATIONS)
msgspec_dict_time = timeit.timeit(run_msgspec_dict, setup=setup_msgspec_dict, number=ITERATIONS)
marshmallow_dict_time = timeit.timeit(run_marshmallow, setup=setup_marshmallow, number=ITERATIONS)
voluptuous_dict_time = timeit.timeit(run_voluptuous, setup=setup_voluptuous, number=ITERATIONS)

monk_invalid_time = timeit.timeit(run_monk_invalid, setup=setup_monk_dict, number=ITERATIONS)
pydantic_invalid_time = timeit.timeit(run_pydantic_invalid, setup=setup_pydantic_dict, number=ITERATIONS)
msgspec_invalid_time = timeit.timeit(run_msgspec_invalid, setup=setup_msgspec_dict, number=ITERATIONS)
marshmallow_invalid_time = timeit.timeit(run_marshmallow_invalid, setup=setup_marshmallow, number=ITERATIONS)
voluptuous_invalid_time = timeit.timeit(run_voluptuous_invalid, setup=setup_voluptuous, number=ITERATIONS)

monk_nested_time = timeit.timeit(run_monk_nested, setup=setup_monk_nested, number=ITERATIONS)
pydantic_nested_time = timeit.timeit(run_pydantic_nested, setup=setup_pydantic_nested, number=ITERATIONS)
msgspec_nested_time = timeit.timeit(run_msgspec_nested, setup=setup_msgspec_nested, number=ITERATIONS)

monk_sanitized_time = timeit.timeit(run_monk_sanitized, setup=setup_monk_dict, number=ITERATIONS)
pydantic_sanitized_time = timeit.timeit(run_pydantic_sanitized, setup=setup_pydantic_dict, number=ITERATIONS)
msgspec_sanitized_time = timeit.timeit(run_msgspec_sanitized, setup=setup_msgspec_dict, number=ITERATIONS)
marshmallow_sanitized_time = timeit.timeit(run_marshmallow_sanitized, setup=setup_marshmallow, number=ITERATIONS)
voluptuous_sanitized_time = timeit.timeit(run_voluptuous_sanitized, setup=setup_voluptuous, number=ITERATIONS)

monk_partial_time = timeit.timeit(run_monk_partial, setup=setup_monk_dict, number=ITERATIONS)
marshmallow_partial_time = timeit.timeit(run_marshmallow_partial, setup=setup_marshmallow, number=ITERATIONS)

monk_func_time = timeit.timeit(run_monk_func, setup=setup_monk_func, number=ITERATIONS)
pydantic_func_time = timeit.timeit(run_pydantic_func, setup=setup_pydantic_func, number=ITERATIONS)

# ---------------------------------------------------------
# Output Markdown Table
# ---------------------------------------------------------
print("### Benchmark Results\n")
print("| Metric | `iron-monk` | `msgspec` | `pydantic` | `attrs` | `marshmallow` | `voluptuous` |")
print("|--------|-------------|-----------|------------|---------|---------------|--------------|")
print(
    f"| **Package Size** | `{monk_size}` | `{msgspec_size}` | `{pydantic_size}` | `{attrs_size}` | `{marshmallow_size}` | `{voluptuous_size}` |"
)
print(
    f"| **Cold Start** | `{monk_import * 1000:.2f}ms` | `{msgspec_import * 1000:.2f}ms` | `{pydantic_import * 1000:.2f}ms` | `{attrs_import * 1000:.2f}ms` | `{marshmallow_import * 1000:.2f}ms` | `{voluptuous_import * 1000:.2f}ms` |"
)
print(
    f"| **Object ({ITERATIONS // 1000}k)** | `{monk_obj_time:.3f}s` | `{msgspec_obj_time:.3f}s` | `{pydantic_obj_time:.3f}s` | `{attrs_obj_time:.3f}s` | N/A | N/A |"
)
print(
    f"| **Dict ({ITERATIONS // 1000}k)** | `{monk_dict_time:.3f}s` | `{msgspec_dict_time:.3f}s` | `{pydantic_dict_time:.3f}s` | N/A | `{marshmallow_dict_time:.3f}s` | `{voluptuous_dict_time:.3f}s` |"
)
print(
    f"| **Nested Dict ({ITERATIONS // 1000}k)** | `{monk_nested_time:.3f}s` | `{msgspec_nested_time:.3f}s` | `{pydantic_nested_time:.3f}s` | N/A | N/A | N/A |"
)
print(
    f"| **Invalid Dict ({ITERATIONS // 1000}k)** | `{monk_invalid_time:.3f}s` | `{msgspec_invalid_time:.3f}s` | `{pydantic_invalid_time:.3f}s` | N/A | `{marshmallow_invalid_time:.3f}s` | `{voluptuous_invalid_time:.3f}s` |"
)
print(
    f"| **Sanitized Dict ({ITERATIONS // 1000}k)** | `{monk_sanitized_time:.3f}s` | `{msgspec_sanitized_time:.3f}s` | `{pydantic_sanitized_time:.3f}s` | N/A | `{marshmallow_sanitized_time:.3f}s` | `{voluptuous_sanitized_time:.3f}s` |"
)
print(
    f"| **Partial Dict ({ITERATIONS // 1000}k)** | `{monk_partial_time:.3f}s` | N/A | N/A | N/A | `{marshmallow_partial_time:.3f}s` | N/A |"
)
print(
    f"| **Function Call ({ITERATIONS // 1000}k)**| `{monk_func_time:.3f}s` | N/A | `{pydantic_func_time:.3f}s` | N/A | N/A | N/A |"
)
