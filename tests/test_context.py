import pytest
from typing import Annotated, Any

from monk import monk, validate, validate_dict
from monk.constraints import (
    Ctx,
    Ref,
    Interval,
    Eq,
    Each,
    DictOf,
    AnyOf,
    Not,
    Len,
)
from monk.exceptions import ValidationError, MissingContextError


# ---------- Ctx in a simple constraint ----------


def test_ctx_in_interval_pass() -> None:
    @monk
    class AgeGate:
        age: Annotated[int, Interval(ge=Ctx("min_age"))]

    obj = AgeGate(age=21)
    validate(obj, context={"min_age": 18})


def test_ctx_in_interval_fail() -> None:
    @monk
    class AgeGate:
        age: Annotated[int, Interval(ge=Ctx("min_age"))]

    obj = AgeGate(age=15)
    with pytest.raises(ValidationError) as exc:
        validate(obj, context={"min_age": 18})

    assert exc.value.errors[0]["field"] == "age"
    assert "18" in exc.value.errors[0]["message"]


def test_ctx_in_eq() -> None:
    @monk
    class Post:
        author_id: Annotated[int, Eq(Ctx("user_id"))]

    validate(Post(author_id=5), context={"user_id": 5})

    with pytest.raises(ValidationError) as exc:
        validate(Post(author_id=99), context={"user_id": 5})

    assert exc.value.errors[0]["field"] == "author_id"


# ---------- Missing context / missing key ----------


def test_missing_context_raises() -> None:
    @monk
    class Post:
        author_id: Annotated[int, Eq(Ctx("user_id"))]

    with pytest.raises(MissingContextError) as exc:
        validate(Post(author_id=5))

    assert "user_id" in str(exc.value)


def test_missing_context_key_aggregates() -> None:
    @monk
    class Post:
        author_id: Annotated[int, Eq(Ctx("user_id"))]

    with pytest.raises(ValidationError) as exc:
        validate(Post(author_id=5), context={"other_key": 1})

    err = exc.value.errors[0]
    assert err["field"] == "author_id"
    assert err["code"] == "MissingContextKey"
    assert "user_id" in err["message"]


# ---------- Ctx + Ref combined on same field ----------


def test_ctx_and_ref_combined() -> None:
    @monk
    class Bid:
        floor: int
        offer: Annotated[int, Interval(gt=Ref("floor"), le=Ctx("ceiling"))]

    # in range
    validate(Bid(floor=10, offer=50), context={"ceiling": 100})

    # below floor
    with pytest.raises(ValidationError):
        validate(Bid(floor=10, offer=10), context={"ceiling": 100})

    # above ceiling
    with pytest.raises(ValidationError):
        validate(Bid(floor=10, offer=200), context={"ceiling": 100})


# ---------- Ctx inside container constraints ----------


def test_ctx_in_each() -> None:
    @monk
    class Allowlist:
        items: Annotated[list[int], Each(Interval(ge=Ctx("min")))]

    validate(Allowlist(items=[5, 10, 15]), context={"min": 5})

    with pytest.raises(ValidationError):
        validate(Allowlist(items=[5, 1, 15]), context={"min": 5})


def test_ctx_in_dictof_value() -> None:
    @monk
    class Scores:
        scores: Annotated[dict[str, int], DictOf(value=Interval(le=Ctx("max")))]

    validate(Scores(scores={"a": 50}), context={"max": 100})

    with pytest.raises(ValidationError):
        validate(Scores(scores={"a": 500}), context={"max": 100})


def test_ctx_in_anyof() -> None:
    @monk
    class Range:
        offer: Annotated[int, AnyOf(Eq(Ctx("a")), Eq(Ctx("b")))]

    validate(Range(offer=5), context={"a": 5, "b": 10})
    validate(Range(offer=10), context={"a": 5, "b": 10})

    with pytest.raises(ValidationError):
        validate(Range(offer=99), context={"a": 5, "b": 10})


def test_ctx_in_not() -> None:
    @monk
    class Restrict:
        value: Annotated[int, Not(Eq(Ctx("forbidden")))]

    validate(Restrict(value=1), context={"forbidden": 0})

    with pytest.raises(ValidationError):
        validate(Restrict(value=0), context={"forbidden": 0})


# ---------- Nested @monk forwarding ----------


def test_context_forwarded_to_nested_monk() -> None:
    @monk
    class Inner:
        n: Annotated[int, Interval(ge=Ctx("min"))]

    @monk
    class Outer:
        inner: Inner

    inner_ok = Inner(n=10)
    validate(inner_ok, context={"min": 5})  # explicit pre-validate

    inner_bad = Inner(n=2)
    outer = Outer(inner=inner_bad)

    with pytest.raises(ValidationError) as exc:
        validate(outer, context={"min": 5})

    assert exc.value.errors[0]["field"].startswith("inner")


# ---------- validate_dict with context ----------


def test_validate_dict_with_context() -> None:
    @monk
    class PostSchema:
        author_id: Annotated[int, Eq(Ctx("user_id"))]
        title: Annotated[str, Len(min_len=1)]

    validate_dict({"author_id": 5, "title": "Hi"}, PostSchema, context={"user_id": 5})

    with pytest.raises(ValidationError) as exc:
        validate_dict({"author_id": 99, "title": "Hi"}, PostSchema, context={"user_id": 5})

    assert exc.value.errors[0]["field"] == "author_id"


def test_validate_dict_missing_context_raises() -> None:
    @monk
    class PostSchema:
        author_id: Annotated[int, Eq(Ctx("user_id"))]

    with pytest.raises(MissingContextError):
        validate_dict({"author_id": 5}, PostSchema)


def test_validate_dict_missing_context_key_aggregates() -> None:
    @monk
    class PostSchema:
        author_id: Annotated[int, Eq(Ctx("user_id"))]

    with pytest.raises(ValidationError) as exc:
        validate_dict({"author_id": 5}, PostSchema, context={"other": 1})

    err = exc.value.errors[0]
    assert err["field"] == "author_id"
    assert err["code"] == "MissingContextKey"


# ---------- __monk_validate__ hook arity ----------


def test_monk_validate_hook_no_context_param_still_works() -> None:
    @monk
    class Post:
        author_id: int
        title: str

        def __monk_validate__(self):  # type: ignore[no-untyped-def]
            if self.title == "bad":
                yield ("title", "Title is forbidden.")

    validate(Post(author_id=1, title="ok"))
    with pytest.raises(ValidationError):
        validate(Post(author_id=1, title="bad"))


def test_monk_validate_hook_receives_context() -> None:
    seen: dict[str, Any] = {}

    @monk
    class Post:
        author_id: int

        def __monk_validate__(self, context):  # type: ignore[no-untyped-def]
            seen["ctx"] = context
            if context is not None and self.author_id != context.get("user_id"):
                yield ("author_id", "Author must match logged-in user.")

    validate(Post(author_id=5), context={"user_id": 5})
    assert seen["ctx"] == {"user_id": 5}

    with pytest.raises(ValidationError) as exc:
        validate(Post(author_id=99), context={"user_id": 5})

    assert exc.value.errors[0]["field"] == "author_id"


def test_monk_validate_hook_context_none_when_not_provided() -> None:
    seen: dict[str, Any] = {}

    @monk
    class Post:
        author_id: int

        def __monk_validate__(self, context):  # type: ignore[no-untyped-def]
            seen["ctx"] = context

    validate(Post(author_id=5))
    assert seen["ctx"] is None


# ---------- Backward compat: no-context users unaffected ----------


def test_existing_ref_validation_still_works_without_context() -> None:
    @monk
    class Pair:
        a: int
        b: Annotated[int, Eq(Ref("a"))]

    validate(Pair(a=1, b=1))
    with pytest.raises(ValidationError):
        validate(Pair(a=1, b=2))


def test_validate_no_context_on_non_ctx_class_works() -> None:
    @monk
    class Simple:
        n: Annotated[int, Interval(ge=0)]

    validate(Simple(n=5))


def test_monk_validate_hook_with_unintrospectable_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If inspect.signature raises (e.g. on certain C-implemented callables), the
    decorator falls back to assuming the hook does NOT want context. Validation
    must still work — calling hook() with no extra args."""
    import inspect as _inspect

    original_signature = _inspect.signature
    seen = {"called": False}

    def flaky_signature(obj):  # type: ignore[no-untyped-def]
        if getattr(obj, "__name__", "") == "__monk_validate__":
            seen["called"] = True
            raise TypeError("fake: signature unavailable")
        return original_signature(obj)

    monkeypatch.setattr(_inspect, "signature", flaky_signature)

    @monk
    class Stub:
        n: int

        def __monk_validate__(self):  # type: ignore[no-untyped-def]
            return None

    assert seen["called"]
    assert Stub.__monk_validate_wants_ctx__ is False  # type: ignore[attr-defined]
    validate(Stub(n=1))
