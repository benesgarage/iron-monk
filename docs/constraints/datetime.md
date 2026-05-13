# Datetime & Schedule

## `Future`
`Future(*, message=None, code=None)` — `datetime` / `date` strictly in the future.

## `IsTzAware` · `IsTzNaive`

Predicate-backed timezone-awareness checks for `datetime` instances. `IsTzAware` requires `tzinfo` set to any zone (use `IsUTC` to require UTC specifically); `IsTzNaive` requires no `tzinfo`.

```python
expires_at: Annotated[datetime.datetime, IsTzAware]
local_time: Annotated[datetime.datetime, IsTzNaive]
```

## `IsUTC`

Predicate-backed marker. Requires a tz-aware `datetime` whose offset is exactly UTC.

```python
created_at: Annotated[datetime.datetime, IsUTC]
```

## `Past`
`Past(*, message=None, code=None)` — `datetime` / `date` strictly in the past.

```python
dob: Annotated[datetime.date, Past]
```

---

## `Cron`
`Cron(*, allow_aws=False, message=None, code=None)` — structurally validates a cron expression. Set `allow_aws=True` to accept the AWS EventBridge 6-field format.

```python
standard:  Annotated[str, Cron()]
eventbridge: Annotated[str, Cron(allow_aws=True)]
```
