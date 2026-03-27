# Performance & Benchmarks

`iron-monk` is a Pure Python validation library. By relying on optimized standard library constructs rather than compiled C/Rust extensions or eval() code-generation, it delivers enterprise-grade speed without the bloat.

## The Results

These benchmarks were run in an isolated virtual environment using **Python 3.13 on an Apple M2 Max**. 

Validations were executed 100,000 times against simple, primitive constraints (e.g., string length and integer intervals) to ensure a fair measurement of framework overhead.

| Metric                    | `iron-monk`<br>*(v0.18.2)* | `msgspec`<br>*(v0.18.6)* | `pydantic`<br>*(v2.10.6)* | `attrs`<br>*(v24.3.0)* | `marshmallow`<br>*(v3.26.1)* |
|---------------------------|----------------------------|--------------------------|---------------------------|------------------------|------------------------------|
| **Package Size**          | `0.06 MB`                  | `0.44 MB`                | `5.91 MB`                 | `0.21 MB`              | `0.17 MB`                    |
| **Cold Start**            | `44.77ms`                  | `52.62ms`                | `83.46ms`                 | `55.73ms`              | `56.01ms`                    |
| **Object (100k)**         | `0.185s`                   | `0.014s`                 | `0.060s`                  | `0.089s`               | N/A                          |
| **Dict (100k)**           | `0.067s`                   | `0.059s`                 | `0.057s`                  | N/A                    | `0.445s`                     |
| **Nested Dict (100k)**    | `0.280s`                   | `0.075s`                 | `0.062s`                  | N/A                    | `1.513s`                     |
| **Invalid Dict (100k)**   | `0.244s`                   | `0.091s`                 | `0.088s`                  | N/A                    | `1.117s`                     |
| **Sanitized Dict (100k)** | `0.083s`                   | `0.070s`                 | `0.058s`                  | N/A                    | `0.450s`                     |
| **Partial Dict (100k)**   | `0.056s`                   | N/A                      | N/A                       | N/A                    | `0.293s`                     |
| **Function Call (100k)**  | `0.162s`                   | N/A                      | `0.065s`                  | N/A                    | N/A                          |

---

## The Deep Dive

### 1. Holistically Best-in-Class
When evaluating features, speed, size, and cold starts together, `iron-monk` is the premier pure-Python validator. It is the *only* library on the board that handles standard objects, raw dicts, deep nesting, dynamic partial updates, automatic sanitization, and function interception natively. It does all of this while processing over **1.3 million dictionaries per second**.

### 2. Microscopic Footprint & Serverless Ready
With **zero** dependencies, `iron-monk` is just 60 KB. It is the fastest library to import, functionally eliminating framework-induced cold starts in Serverless environments like AWS Lambda.

### 3. Why `attrs` is faster at Object Instantiation
`attrs` relies on Code Generation, dynamically compiling custom Python strings into memory via `eval()`. `iron-monk` strictly avoids `eval()`, accepting a microsecond of runtime overhead to keep the codebase clean while aggregating errors.

### 4. Why `msgspec` and `pydantic` win on raw CPU loops
Compiled C/Rust cores will always defeat CPython bytecode. However, this speed costs massive dependency sizes and rigidity. As a native Python citizen, `iron-monk` can dynamically validate `PATCH` updates, instantly sanitize dictionaries, and seamlessly execute standalone constraints natively.

---

## Run it yourself!

We believe in complete transparency. Run this inside a fresh virtual environment to verify the numbers on your own machine:

```bash
# 1. Create a clean project
mkdir monk_benchmarks && cd monk_benchmarks
uv init
uv python pin 3.13

# 2. Install the competitors and iron-monk directly from PyPI
uv add iron-monk msgspec pydantic attrs marshmallow

# 3. Download and run the benchmark script
curl -O https://raw.githubusercontent.com/benesgarage/iron-monk/main/support/benchmark.py
uv run benchmark.py
```