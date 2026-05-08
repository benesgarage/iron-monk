# Performance & Benchmarks

`iron-monk` is a pure-Python validation library. It relies on optimized standard-library constructs — no compiled C/Rust extensions, no `eval()`-based code generation, no compilation toolchain at install time. The cost is a few microseconds of pure-Python overhead in tight loops; the payoff is faster cold starts and zero dependency baggage.

## Methodology

Benchmarks were run on **Python 3.13, Apple M2 Max**, in an isolated virtual environment. Each scenario executes 100,000 validations against a small primitive schema (string length + integer interval) so framework overhead is what is being measured, not user code.

The full script lives at [`support/benchmark.py`](https://github.com/benesgarage/iron-monk/blob/main/support/benchmark.py).

## Results

| Metric | `iron-monk` *(0.24.0)* | `msgspec` *(0.21.1)* | `pydantic` *(2.13.4)* | `attrs` *(26.1.0)* | `marshmallow` *(4.3.0)* |
| --- | --- | --- | --- | --- | --- |
| **Package Size** | `0.09 MB` | `0.44 MB` | `5.88 MB` | `0.21 MB` | `0.17 MB` |
| **Cold Start** | `34.50ms` | `38.21ms` | `65.08ms` | `41.06ms` | `59.39ms` |
| **Object (100k)** | `0.233s` | `0.013s` | `0.052s` | `0.082s` | N/A |
| **Dict (100k)** | `0.087s` | `0.057s` | `0.049s` | N/A | `0.426s` |
| **Nested Dict (100k)** | `0.340s` | `0.071s` | `0.053s` | N/A | `1.383s` |
| **Invalid Dict (100k)** | `0.244s` | `0.081s` | `0.073s` | N/A | `1.001s` |
| **Sanitized Dict (100k)** | `0.105s` | `0.063s` | `0.054s` | N/A | `0.439s` |
| **Partial Dict (100k)** | `0.058s` | N/A | N/A | N/A | `0.267s` |
| **Function Call (100k)** | `0.168s` | N/A | `0.050s` | N/A | N/A |

---

## What the numbers mean

### Holistically best-in-class for pure-Python

`iron-monk` is the only library on the board that natively handles standard objects, raw dicts, deeply nested schemas, dynamic partial updates, payload sanitization, and function interception — in a single zero-dependency package. It validates over **1.3 million dictionaries per second** while still aggregating every error into a single response.

### Serverless-ready cold starts

With zero dependencies, `iron-monk` is the fastest library on this list to import. In serverless environments where every millisecond of cold-start latency matters, the dependency tax of `pydantic` or `msgspec` is a real bill that `iron-monk` does not charge.

### Why `attrs` wins on object instantiation

`attrs` generates Python source strings and compiles them with `eval()` at class-definition time. `iron-monk` deliberately does not — keeping the codebase auditable and free of dynamic codegen costs a few microseconds per object.

### Why `msgspec` and `pydantic` win on raw loops

Both ship compiled C/Rust cores that beat CPython bytecode on hot loops. The trade-off is dependency size, install complexity, and rigidity around dynamic features (PATCH semantics, raw-dict sanitization, standalone constraint execution). For most application workloads, `iron-monk`'s pure-Python overhead is invisible next to network or database latency — and you keep the ergonomics.

---

## Run it yourself

The benchmark script is reproducible. Run it inside a fresh virtual environment to verify the numbers on your hardware:

```bash
mkdir monk_benchmarks && cd monk_benchmarks
uv init
uv python pin 3.13

uv add iron-monk msgspec pydantic attrs marshmallow

curl -O https://raw.githubusercontent.com/benesgarage/iron-monk/main/support/benchmark.py
uv run benchmark.py
```
