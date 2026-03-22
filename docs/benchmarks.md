# Performance & Benchmarks

`iron-monk` is built to be a **Pure Python** validation library. It refuses to use compiled C/Rust extensions, and it refuses to use heavy `eval()` code-generation magic. 

Despite this strict "Zero Magic" philosophy, `iron-monk` is designed to be fast. By relying on optimized standard library constructs (like native `@dataclass` generation and structural recursion loops), it delivers enterprise-grade speed without the bloat.

## The Results

These benchmarks were run in an isolated virtual environment using **Python 3.13 on an Apple M2 Max**. 

Validations were executed 100,000 times against simple, primitive constraints (e.g., string length and integer intervals) to ensure a fair measurement of framework overhead.

| Metric                               | `iron-monk`<br>*(v0.16.1)* | `msgspec`<br>*(v0.18.6)* | `pydantic`<br>*(v2.10.6)* | `attrs`<br>*(v24.3.0)* | `marshmallow`<br>*(v3.26.1)* |
|--------------------------------------|----------------------------|--------------------------|---------------------------|------------------------|------------------------------|
| **Package Size**                     | `0.04 MB`                  | `0.44 MB`                | `5.91 MB`                 | `0.21 MB`              | `0.17 MB`                    | `0.09 MB` |
| **Cold Start**                       | `32.05ms`                  | `36.96ms`                | `61.59ms`                 | `38.78ms`              | `40.00ms`                    |
| **Object Validation (100k)**         | `0.170s`                   | `0.012s`                 | `0.054s`                  | `0.083s`               | N/A                          |
| **Dict Validation (100k)**           | `0.075s`                   | `0.055s`                 | `0.051s`                  | N/A                    | `0.410s`                     |
| **Nested Dict Validation (100k)**    | `0.388s`                   | `0.028s`                 | `0.131s`                  | N/A                    | `1.379s`                     |
| **Invalid Dict Validation (100k)**   | `0.234s`                   | `0.079s`                 | `0.077s`                  | N/A                    | `0.993s`                     |
| **Sanitized Dict Validation (100k)** | `0.087s`                   | `0.058s`                 | `0.052s`                  | N/A                    | `0.412s`                     |
| **Partial Dict Validation (100k)**   | `0.059s`                   | N/A                      | N/A                       | N/A                    | `0.276s`                     |
| **Function Validation (100k)**       | `0.155s`                   | N/A                      | `0.055s`                  | N/A                    | N/A                          |

---

## The Deep Dive

### 1. Pure Python
Best-in-class pure-Python framework, able to process over **1.3 million dictionaries per second** (`0.075s` for 100k dicts).

### 2. Microscopic Footprint & Serverless Ready
Because `iron-monk` has **zero dependencies**, it takes up less disk space than a small image (`40 KB`). This makes it the fastest library to import, meaning it eliminates framework-induced cold starts in Serverless environments like AWS Lambda or Google Cloud Functions.

### 3. Why `attrs` is faster at Object Instantiation
You will notice that `attrs` creates objects incredibly quickly (`0.083s`). This is because `attrs` uses a technique called **Code Generation**. Under the hood, it writes a custom Python script as a string and dynamically compiles it into memory using `eval()`.

`iron-monk` intentionally avoids using `eval()` to stay true to its "Zero Magic" architecture. Instead, it uses standard structural looping. By accepting a tiny fraction of a second in runtime overhead, `iron-monk` keeps its codebase entirely free of dynamic execution hacks while gaining the ability to holistically aggregate errors.

### 4. Why `msgspec` and `pydantic` win on raw CPU loops
`msgspec` is written in C, and `pydantic-core` is written in Rust. In raw CPU micro-benchmarks, compiled systems languages will always defeat CPython bytecode. 

However, this speed comes at a cost: massive dependency sizes, slower import times, and less flexibility. Because `iron-monk` is a native Python citizen, it can dynamically validate `PATCH` updates, instantly sanitize dictionaries, and seamlessly execute standalone constraints—things compiled schemas struggle to do dynamically at runtime.

---

## Run it yourself!

We believe in complete transparency. If you want to verify these numbers on your own machine, you can run the exact gauntlet we use.

To ensure a fair test that ignores local development cache artifacts, run this inside a fresh, clean virtual environment:

```bash
# 1. Create a clean project
mkdir monk_benchmarks && cd monk_benchmarks
uv init
uv python pin 3.13

# 2. Install the competitors and iron-monk directly from PyPI
uv add iron-monk msgspec pydantic attrs marshmallow voluptuous

# 3. Download and run the benchmark script
curl -O https://raw.githubusercontent.com/benesgarage/iron-monk/main/support/benchmark.py
uv run benchmark.py
```