# Contributing to iron-monk

First off, thank you for considering contributing to `iron-monk`!

## Development Setup

We use a `Makefile` to make local development incredibly simple.

1. **Fork and clone** the repository.
2. **Install dependencies** in a virtual environment:
   ```bash
   make install
   ```

## Making Changes

`iron-monk` is heavily focused on strict typing, zero-dependency performance, and testing. If you are adding a new constraint, please ensure it includes:
- Success tests
- Failure tests (`ValueError`)
- Type mismatch tests (`TypeError`)

## Before Submitting a Pull Request

Before you push your changes, please run our universal check command. This will format your code with Ruff, lint it, check the static typing with MyPy, and run the pytest suite:

```bash
make check
```
If this passes, your PR is ready to go!