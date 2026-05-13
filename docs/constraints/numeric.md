# Numeric

## `DecimalPlaces`
`DecimalPlaces(max_places, *, message=None, code=None)` — caps the digits after the decimal point. Accepts `int`, `float`, `decimal.Decimal`, and numeric strings. Trailing zeros count as places (so `Decimal("1.50")` reports 2 places).

```python
price: Annotated[Decimal, DecimalPlaces(max_places=2)]
```

## `Even` · `Odd`

Integer parity checks. Reject `bool` and non-integer numerics.

```python
batch: Annotated[int, Even]
seat:  Annotated[int, Odd]
```

## `Interval`
`Interval(*, gt=None, ge=None, lt=None, le=None, message=None, code=None)` — comparable bounds. Any combination of bounds is valid. All bounds accept `Ref`.

```python
quantity: Annotated[int, Interval(gt=0, le=100)]
```

## `IsFinite` · `IsInfinite` · `IsNan`

Predicate-backed math checks for floats. Use bare instances.

```python
ratio: Annotated[float, IsFinite]
```

## `MultipleOf`
`MultipleOf(multiple_of, *, message=None, code=None)` — value must be exactly divisible. Accepts `Ref`.

```python
pack_size: Annotated[int, MultipleOf(5)]
```

## `NonNegative` · `Positive` · `Negative`

Pre-instantiated `Interval` shortcuts: `ge=0`, `gt=0`, and `lt=0` respectively. Use bare.

```python
score:   Annotated[int, NonNegative]
amount:  Annotated[float, Positive]
delta:   Annotated[float, Negative]
```

## `NonZero`
`NonZero(*, message=None, code=None)` — rejects values equal to zero. Works with any numeric that supports `==`.

```python
divisor: Annotated[float, NonZero]
```

## `Port`
`Port(*, message=None, code=None)` — integer in `[1, 65535]`.

```python
db_port: Annotated[int, Port]
```

## `PowerOfTwo`
`PowerOfTwo(*, message=None, code=None)` — positive integer that is a power of two (1, 2, 4, 8, 16, …). Common for ML batch sizes, ring buffers, and cache-aligned allocations.

```python
batch_size: Annotated[int, PowerOfTwo]
```
