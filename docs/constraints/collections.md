# Collections

## `AllEqual`
`AllEqual(*, message=None, code=None)` — every element in the iterable must equal the others. Empty iterables pass. Rejects exhaustible iterators.

```python
all_same: Annotated[list[int], AllEqual]
```

## `Contains`
`Contains(item, *, message=None, code=None)` — collection or string must contain `item` / substring. Accepts `Ref`.

```python
categories: Annotated[list[str], Contains("default")]
```

## `ContainsKeys`
`ContainsKeys(keys, *, message=None, code=None)` — dict must include all `keys`. Accepts `Ref`.

```python
payload: Annotated[dict, ContainsKeys(["id", "type"])]
```

## `CSV`
`CSV(*constraints, separator=",", unique=False, message=None, code=None)` — splits a delimited string in place and applies `constraints` to each element. Composes recursively (`CSV(CSV(...), ...)`).

```python
tags: Annotated[str, CSV(LowerCase, Len(min_len=2), separator=",")]
matrix: Annotated[str, CSV(CSV(LowerCase, separator="|"), separator=",")]
```

## `ExactLen`
`ExactLen(length, *, message=None, code=None)` — exact length. Accepts `Ref`.

```python
pin: Annotated[str, ExactLen(4)]
```

## `Len`
`Len(min_len=0, max_len=None, *, message=None, code=None)` — bounded length. Both bounds accept `Ref`.

```python
tags: Annotated[list[str], Len(min_len=1, max_len=10)]
```

## `Nested`
`Nested(schema, partial=False, *, message=None, code=None)` — validates a raw dict against another `TypedDict` / `@monk` class. Use `partial=True` for PATCH-style payloads.

```python
class AddressDict(TypedDict):
    city: str

address: Annotated[AddressDict, Nested(AddressDict)]
```

## `NonEmpty`

Pre-instantiated alias for `Len(min_len=1)`. Works on any sized container (string, list, dict, set, tuple). Use bare.

```python
tags: Annotated[list[str], NonEmpty]
name: Annotated[str, NonEmpty]
```

## `Sorted`
`Sorted(reverse=False, *, message=None, code=None)` — iterable items must be in non-decreasing order (or non-increasing when `reverse=True`). Equal neighbors are allowed. Rejects exhaustible iterators — convert to a `list`/`tuple` first.

```python
timestamps: Annotated[list[int], Sorted]
leaderboard: Annotated[list[int], Sorted(reverse=True)]
```

## `Subset`
`Subset(choices, *, message=None, code=None)` — every element must lie within `choices`. Accepts `Ref`. Backed by a `frozenset` for O(n) checks.

```python
permissions: Annotated[list[str], Subset(["read", "write", "execute"])]
```

## `Unique`
`Unique(*, message=None, code=None)` — all elements distinct. Falls back gracefully for unhashable items.

```python
matrix: Annotated[list[list[int]], Unique]
```
