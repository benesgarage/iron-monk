# Geospatial

## `LatLong`
`LatLong(*, message=None, code=None)` — sequence of exactly two floats: `(lat, long)`, with `lat ∈ [-90, 90]` and `long ∈ [-180, 180]`.

```python
coords: Annotated[tuple[float, float], LatLong]
```
