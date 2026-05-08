"""Targeted tests for the auto-synthesis internals in monk.operations.

These tests cover degenerate / corner cases that are hard to reach via the
public decorator surface, ensuring 100% line coverage of the synthesis
helpers (`_TupleSchema`, `_compile_inner_validator`,
`_synthesize_container_constraint`, `_UnionRouter`).
"""

import types
from typing import Annotated, Any
from unittest.mock import patch

import pytest

from monk import monk, settings
from monk.constraints import Interval, Len, Nullable
from monk.exceptions import ValidationError
from monk.operations import (
    _TupleSchema,  # pyright: ignore[reportPrivateUsage]
    _compile_inner_validator,  # pyright: ignore[reportPrivateUsage]
    _synthesize_container_constraint,  # pyright: ignore[reportPrivateUsage]
)


# ---------------------------------------------------------------------------
# _TupleSchema branches
# ---------------------------------------------------------------------------


def test_tupleschema_rejects_non_tuple() -> None:
    schema = _TupleSchema([([Interval(gt=0)], False)])
    with pytest.raises(TypeError, match="not a tuple"):
        schema.validate([1])  # list, not tuple


def test_tupleschema_skips_positions_with_no_rule() -> None:
    """tuple[int, Annotated[str, Len]] — index 0 has no metadata, index 1 does."""

    @monk(defer=False)
    class Box:
        pair: tuple[int, Annotated[str, Len(min_len=2)]]

    Box(pair=(99, "ok"))

    with pytest.raises(ValidationError) as exc:
        Box(pair=(99, "x"))
    assert exc.value.errors[0]["field"] == "pair[1]"


def test_tupleschema_allows_none_when_inner_is_optional() -> None:
    @monk(defer=False)
    class Box:
        pair: tuple[Annotated[int, Interval(gt=0)] | None, Annotated[str, Len(min_len=1)]]

    Box(pair=(None, "ok"))


def test_tupleschema_rejects_none_when_inner_is_required() -> None:
    @monk(defer=False)
    class Box:
        pair: tuple[Annotated[int, Interval(gt=0)], Annotated[str, Len(min_len=1)]]

    with pytest.raises(ValidationError) as exc:
        Box(pair=(None, "ok"))  # type: ignore[arg-type]
    assert exc.value.errors[0]["code"] == "NotNull"
    assert exc.value.errors[0]["field"] == "pair[0]"


def test_tupleschema_propagates_inner_validation_error() -> None:
    """A constraint that raises ValidationError (not ValueError) should have
    its per-element field paths concatenated into the tuple position."""

    class _AggregatingConstraint:
        code = "Multi"

        def validate(self, value: Any) -> None:
            raise ValidationError([{"field": "[inner]", "message": "bad", "code": "Multi"}])

    schema = _TupleSchema([([_AggregatingConstraint()], False)])
    with pytest.raises(ValidationError) as exc:
        schema.validate(("anything",))
    assert exc.value.errors[0]["field"] == "[0][inner]"


# ---------------------------------------------------------------------------
# _compile_inner_validator — settings.type_metadata fast path
# ---------------------------------------------------------------------------


def test_inner_validator_picks_up_type_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """settings.type_metadata constraints attached to the bare element type
    should be applied during inner-validator compilation."""

    monkeypatch.setattr(settings, "type_metadata", {int: [Interval(gt=0)]})

    @monk(defer=False)
    class Box:
        items: list[int]

    Box(items=[1, 2, 3])

    with pytest.raises(ValidationError):
        Box(items=[1, 0, 3])


# ---------------------------------------------------------------------------
# Union recursion — branches with container origin (b_origin not None)
# and branches with no compiled validator
# ---------------------------------------------------------------------------


def test_union_branch_with_bare_class_uses_origin_for_isinstance() -> None:
    """Union branch typed as a bare container without inner annotations:
    `_compile_inner_validator` returns None for that branch, but the branch
    is still appended with an empty constraint list so isinstance routing
    works at validation time."""

    @monk(defer=False)
    class Box:
        payload: list[Annotated[int, Interval(gt=0)]] | str

    Box(payload=[1, 2, 3])
    Box(payload="hello")

    with pytest.raises(ValidationError):
        Box(payload=[0, -1])


# ---------------------------------------------------------------------------
# _synthesize_container_constraint — degenerate / direct-call paths
# ---------------------------------------------------------------------------


def test_synth_returns_none_for_non_container_hint() -> None:
    assert _synthesize_container_constraint(int) is None


def test_synth_returns_none_for_dict_with_wrong_arity() -> None:
    """dict with malformed args is a no-op rather than a crash."""
    # types.GenericAlias bypasses dict's normal arity check while still
    # producing something `typing.get_origin` recognizes as `dict`.
    fake_dict_one_arg = types.GenericAlias(dict, (int,))
    assert _synthesize_container_constraint(fake_dict_one_arg) is None


def test_synth_returns_none_for_dict_without_inner_annotations() -> None:
    """dict[str, int] has no inner Annotated metadata anywhere — synthesis
    must return None so the field stays unvalidated."""
    assert _synthesize_container_constraint(dict[str, int]) is None


def test_synth_returns_none_for_variadic_tuple_with_bare_inner() -> None:
    assert _synthesize_container_constraint(tuple[int, ...]) is None


def test_synth_variadic_tuple_with_optional_inner_attaches_nullable() -> None:
    """tuple[Annotated[int, Interval] | None, ...] — synth must build an
    Each(...) that allows None per element."""

    @monk(defer=False)
    class Box:
        coords: tuple[Annotated[int, Interval(gt=0)] | None, ...]

    Box(coords=(1, None, 2))

    with pytest.raises(ValidationError):
        Box(coords=(1, 0, 3))


def test_synth_skips_typevartuple() -> None:
    """PEP 646 Unpack / TypeVarTuple positional args silently skip synthesis."""

    class _FakeTypeVarTuple:
        pass

    _FakeTypeVarTuple.__name__ = "TypeVarTuple"
    fake_hetero = types.GenericAlias(tuple, (_FakeTypeVarTuple(),))
    assert _synthesize_container_constraint(fake_hetero) is None


def test_synth_swallows_exceptions_during_hetero_compile() -> None:
    """If `_compile_inner_validator` raises while compiling a positional
    tuple arg, synthesis returns None instead of crashing decoration."""

    fake_hetero = types.GenericAlias(tuple, (int, str))
    with patch(
        "monk.operations._compile_inner_validator",
        side_effect=RuntimeError("boom"),
    ):
        assert _synthesize_container_constraint(fake_hetero) is None


def test_synth_returns_none_for_hetero_tuple_with_no_validation() -> None:
    """tuple[int, str] — neither position carries validation. Synthesis is
    a no-op."""
    assert _synthesize_container_constraint(tuple[int, str]) is None


def test_synth_returns_none_for_list_with_only_optional_inner() -> None:
    """`list[T | None]` where T has no constraints: nothing to enforce
    per-element except nullability, which the outer Union/None handling
    already covers. Synth returns None."""
    assert _synthesize_container_constraint(list[int | None]) is None


# ---------------------------------------------------------------------------
# _compile_inner_validator — direct-call sanity
# ---------------------------------------------------------------------------


def test_compile_inner_returns_none_for_bare_type() -> None:
    assert _compile_inner_validator(int) is None


def test_compile_inner_handles_optional_marker() -> None:
    """Annotated[int, Nullable] should compile to ([], True)."""
    result = _compile_inner_validator(Annotated[int, Nullable])
    assert result is not None
    constraints, allow_none = result
    assert constraints == []
    assert allow_none is True


def test_union_inside_container_uses_origin_for_isinstance() -> None:
    """When a Union appears nested inside another container, the inner
    `_compile_inner_validator` peels the container origin (e.g. `list`)
    out of each branch so the routed `_UnionRouter` can `isinstance`-check
    it at validation time."""

    @monk(defer=False)
    class Box:
        nested: list[list[Annotated[int, Interval(gt=0)]] | str]

    Box(nested=[[1, 2], "ok"])

    with pytest.raises(ValidationError):
        Box(nested=[[0, -1]])


def test_synth_returns_none_for_dict_with_only_optional_inner() -> None:
    """dict[Annotated[K, Nullable], Annotated[V, Nullable]] — both inner
    compiles produce ([], allow_none=True). With no constraints to enforce,
    synthesis returns None."""
    hint = dict[Annotated[str, Nullable], Annotated[int, Nullable]]
    assert _synthesize_container_constraint(hint) is None


def test_synth_returns_none_for_variadic_tuple_with_only_optional_inner() -> None:
    """tuple[Annotated[int, Nullable], ...] — inner is `([], True)`;
    nothing to enforce per element, so synthesis returns None."""
    hint = tuple[Annotated[int, Nullable], ...]
    assert _synthesize_container_constraint(hint) is None
