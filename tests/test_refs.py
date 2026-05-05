import pytest
from typing import Annotated, Any

from monk import monk, validate
from monk.operations import validate_dict, validate_arguments, _extract_monk_metadata  # pyright: ignore[reportPrivateUsage]
from typing import get_type_hints
from monk.constraints import (
    Eq,
    Not,
    Interval,
    Len,
    Ref,
    Each,
    AnyOf,
    MultipleOf,
    StartsWith,
    EndsWith,
    Contains,
    OneOf,
    Subset,
    ExactLen,
    ContainsKeys,
    CSV,
    DictOf,
)
from monk.exceptions import ValidationError
from monk.config import settings


def test_eq_ref_success() -> None:
    @monk
    class Registration:
        password: str
        confirm_password: Annotated[str, Eq(Ref("password"))]

    user = Registration(password="secret", confirm_password="secret")
    validate(user)  # Should pass seamlessly


def test_eq_ref_failure() -> None:
    @monk
    class Registration:
        password: str
        confirm_password: Annotated[str, Eq(Ref("password"))]

    user = Registration(password="secret", confirm_password="wrong")

    with pytest.raises(ValidationError) as exc:
        validate(user)

    assert exc.value.errors[0]["field"] == "confirm_password"
    assert "Must be equal to secret" in exc.value.errors[0]["message"]


def test_interval_ref() -> None:
    @monk
    class AuctionBid:
        starting_price: float
        offer: Annotated[float, Interval(gt=Ref("starting_price"))]

    # Pass condition
    validate(AuctionBid(starting_price=10.0, offer=15.0))

    # Fail condition
    with pytest.raises(ValidationError) as exc:
        validate(AuctionBid(starting_price=10.0, offer=5.0))

    assert "Must be greater than 10.0" in exc.value.errors[0]["message"]


def test_len_ref() -> None:
    @monk
    class Team:
        max_members: int
        members: Annotated[list[str], Len(max_len=Ref("max_members"))]

    # Pass condition (exactly max length)
    validate(Team(max_members=2, members=["Alice", "Bob"]))

    # Fail condition
    with pytest.raises(ValidationError) as exc:
        validate(Team(max_members=1, members=["Alice", "Bob"]))

    assert "Must have a maximum length of 1" in exc.value.errors[0]["message"]


def test_thread_safety_constraint_mutation() -> None:
    """
    Ensures that evaluating a Ref does not permanently modify the cached constraint singleton.
    """

    @monk
    class AuctionBid:
        starting_price: float
        offer: Annotated[float, Interval(gt=Ref("starting_price"))]

    # First execution sets the resolved Ref internally
    bid1 = AuctionBid(starting_price=10.0, offer=15.0)
    validate(bid1)

    # If the constraint singleton was mutated, `gt` would still be 10.0 and this would incorrectly pass!
    bid2 = AuctionBid(starting_price=20.0, offer=15.0)
    with pytest.raises(ValidationError):
        validate(bid2)


def test_validate_dict_with_refs() -> None:
    """
    Ensures that raw dictionary validation accurately resolves references against sibling dictionary keys.
    """

    @monk
    class UpdateEmail:
        old_email: str
        new_email: Annotated[str, Not(Eq(Ref("old_email")))]

    # Pass
    validate_dict({"old_email": "a@a.com", "new_email": "b@b.com"}, UpdateEmail)

    # Fail
    with pytest.raises(ValidationError) as exc:
        validate_dict({"old_email": "a@a.com", "new_email": "a@a.com"}, UpdateEmail)
    assert exc.value.errors[0]["field"] == "new_email"


def test_multiple_refs() -> None:
    """Ensures a single constraint can resolve multiple Ref objects simultaneously."""

    @monk
    class TemperatureRange:
        min_temp: float
        max_temp: float
        current: Annotated[float, Interval(gt=Ref("min_temp"), lt=Ref("max_temp"))]

    # Pass
    validate(TemperatureRange(min_temp=0.0, max_temp=100.0, current=50.0))

    # Fail gt
    with pytest.raises(ValidationError) as exc:
        validate(TemperatureRange(min_temp=50.0, max_temp=100.0, current=40.0))
    assert "Must be greater than 50.0" in exc.value.errors[0]["message"]

    # Fail lt
    with pytest.raises(ValidationError) as exc:
        validate(TemperatureRange(min_temp=0.0, max_temp=50.0, current=60.0))
    assert "Must be less than 50.0" in exc.value.errors[0]["message"]


def test_missing_ref_field_resolves_to_none() -> None:
    """Ensures that referencing an omitted dictionary key resolves to None."""

    @monk
    class Compare:
        value: Annotated[str, Eq(Ref("target"))]
        target: str | None = None

    # 'target' is missing in the dict, so it resolves to None. "A" != None, so this raises correctly
    with pytest.raises(ValidationError) as exc:
        validate_dict({"value": "A"}, Compare)

    assert exc.value.errors[0]["field"] == "value"
    assert "Must be equal to None" in exc.value.errors[0]["message"]


def test_not_eq_ref() -> None:
    @monk
    class ChangePassword:
        old_password: str
        new_password: Annotated[str, Not(Eq(Ref("old_password")))]

    validate(ChangePassword(old_password="abc", new_password="def"))

    with pytest.raises(ValidationError):
        validate(ChangePassword(old_password="abc", new_password="abc"))


def test_ref_resolves_to_none_ignores_constraint() -> None:
    """Ensures constraints like Interval correctly ignore bounds when the Ref resolves to None."""

    @monk
    class Event:
        end_time: Annotated[int, Interval(gt=Ref("start_time"))]
        start_time: int | None = None

    # start_time is None, so gt=None. Interval natively ignores None bounds.
    validate(Event(start_time=None, end_time=5))

    # start_time is 10, so gt=10. This must fail because 5 is not greater than 10.
    with pytest.raises(ValidationError):
        validate(Event(start_time=10, end_time=5))


def test_ref_inside_each_type_metadata() -> None:
    """Tests if Ref can be resolved when deeply nested inside container constraints like Each."""

    @monk
    class Group:
        max_size: int
        items: Annotated[list[str], Each(Len(max_len=Ref("max_size")))]

    # Should pass
    validate(Group(max_size=3, items=["a", "ab", "abc"]))

    # Should fail
    with pytest.raises(ValidationError) as exc:
        validate(Group(max_size=3, items=["a", "abcd"]))
    assert "Must have a maximum length of 3" in exc.value.errors[0]["message"]


def test_ref_inside_anyof_type_metadata() -> None:
    """Tests if Ref can be resolved when nested inside logical operators like AnyOf."""

    @monk
    class Configuration:
        allowed_version: int
        version: Annotated[int, AnyOf(Eq(0), Eq(Ref("allowed_version")))]

    # Should pass
    validate(Configuration(allowed_version=5, version=5))
    validate(Configuration(allowed_version=5, version=0))

    # Should fail
    with pytest.raises(ValidationError):
        validate(Configuration(allowed_version=5, version=3))


def test_ref_with_unwrapped_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests if Ref accurately resolves and unwraps values from the host instance."""

    class MockWrapper:
        def __init__(self, value: Any) -> None:
            self.value = value

    original_unwrap = settings.unwrap

    def mock_unwrap(item: Any) -> Any:
        if isinstance(item, MockWrapper):
            return item.value
        return original_unwrap(item)

    monkeypatch.setattr(settings, "unwrap", mock_unwrap)

    @monk
    class Profile:
        target_status: Any
        status: Annotated[str, Eq(Ref("target_status"))]

    # Ref should fetch MockWrapper("active") and unwrap it to "active" seamlessly!
    validate(Profile(target_status=MockWrapper("active"), status="active"))


def test_multiple_of_ref() -> None:
    """Ensures MultipleOf can dynamically resolve bounds, and handles zero-division gracefully."""

    @monk
    class BatchOrder:
        batch_size: int
        quantity: Annotated[int, MultipleOf(Ref("batch_size"))]

    # Pass
    validate(BatchOrder(batch_size=12, quantity=36))

    # Fail modulo
    with pytest.raises(ValidationError) as exc:
        validate(BatchOrder(batch_size=12, quantity=30))
    assert "Must be a multiple of 12" in exc.value.errors[0]["message"]

    # Fail division by zero
    with pytest.raises(ValidationError) as exc:
        validate(BatchOrder(batch_size=0, quantity=10))
    assert "multiple_of cannot be 0" in exc.value.errors[0]["message"]


def test_startswith_ref() -> None:
    @monk
    class URLValidator:
        base_url: str
        full_url: Annotated[str, StartsWith(Ref("base_url"))]

    validate(URLValidator(base_url="https://api.com", full_url="https://api.com/v1/users"))

    with pytest.raises(ValidationError) as exc:
        validate(URLValidator(base_url="https://api.com", full_url="http://api.com/v1/users"))

    assert "Must start with" in exc.value.errors[0]["message"]


def test_endswith_ref() -> None:
    @monk
    class EmailFilter:
        domain: str
        email: Annotated[str, EndsWith(Ref("domain"))]

    validate(EmailFilter(domain="@ironmonk.dev", email="kai@ironmonk.dev"))

    with pytest.raises(ValidationError) as exc:
        validate(EmailFilter(domain="@ironmonk.dev", email="kai@gmail.com"))

    assert "Must end with" in exc.value.errors[0]["message"]


def test_contains_ref() -> None:
    @monk
    class SearchQuery:
        keyword: str
        text: Annotated[str, Contains(Ref("keyword"))]

    validate(SearchQuery(keyword="monk", text="iron-monk is fast!"))

    with pytest.raises(ValidationError) as exc:
        validate(SearchQuery(keyword="pydantic", text="iron-monk is fast!"))

    assert "Must contain" in exc.value.errors[0]["message"]


def test_oneof_ref() -> None:
    @monk
    class Election:
        nominees: list[str]
        winner: Annotated[str, OneOf(Ref("nominees"))]

    validate(Election(nominees=["Alice", "Bob"], winner="Alice"))

    with pytest.raises(ValidationError) as exc:
        validate(Election(nominees=["Alice", "Bob"], winner="Charlie"))

    assert "Must be one of" in exc.value.errors[0]["message"]


def test_subset_ref() -> None:
    @monk
    class PizzaOrder:
        available_toppings: list[str]
        chosen_toppings: Annotated[list[str], Subset(Ref("available_toppings"))]

    validate(PizzaOrder(available_toppings=["cheese", "pepperoni", "bacon"], chosen_toppings=["cheese", "bacon"]))

    with pytest.raises(ValidationError) as exc:
        validate(PizzaOrder(available_toppings=["cheese", "pepperoni"], chosen_toppings=["pineapple"]))

    assert "Contains unallowed items" in exc.value.errors[0]["message"]


def test_exactlen_ref() -> None:
    @monk
    class CodeVerification:
        code_length: int
        code: Annotated[str, ExactLen(Ref("code_length"))]

    validate(CodeVerification(code_length=6, code="123456"))

    with pytest.raises(ValidationError) as exc:
        validate(CodeVerification(code_length=6, code="12345"))

    assert "Must have an exact length of 6" in exc.value.errors[0]["message"]


def test_containskeys_ref() -> None:
    @monk
    class ConfigValidator:
        required_fields: list[str]
        config_data: Annotated[dict[str, Any], ContainsKeys(Ref("required_fields"))]

    validate(ConfigValidator(required_fields=["host", "port"], config_data={"host": "localhost", "port": 8080}))

    with pytest.raises(ValidationError) as exc:
        validate(ConfigValidator(required_fields=["host", "port"], config_data={"host": "localhost"}))

    assert "Dictionary is missing required keys" in exc.value.errors[0]["message"]


def test_csv_ref_in_constraints() -> None:
    """Ensures that Ref resolves correctly when nested inside the inner constraints of CSV."""

    @monk
    class TagUpload:
        required_prefix: str
        tags: Annotated[str, CSV(StartsWith(Ref("required_prefix")))]

    validate(TagUpload(required_prefix="aws:", tags="aws:env,aws:prod"))

    with pytest.raises(ValidationError) as exc:
        validate(TagUpload(required_prefix="aws:", tags="aws:env,gcp:prod"))

    assert "Must start with" in exc.value.errors[0]["message"]


def test_dictof_ref_in_constraints() -> None:
    """Ensures that Ref resolves correctly when nested inside the key/value constraints of DictOf."""

    @monk
    class Thresholds:
        min_value: int
        metrics: Annotated[dict[str, int], DictOf(value=Interval(gt=Ref("min_value")))]

    validate(Thresholds(min_value=10, metrics={"cpu": 15, "ram": 20}))

    with pytest.raises(ValidationError) as exc:
        validate(Thresholds(min_value=10, metrics={"cpu": 15, "ram": 5}))

    assert "Must be greater than" in exc.value.errors[0]["message"]


def test_oneof_empty_ref() -> None:
    @monk
    class Election:
        nominees: list[str]
        winner: Annotated[str, OneOf(Ref("nominees"))]

    with pytest.raises(ValidationError) as exc:
        validate(Election(nominees=[], winner="Alice"))
    assert "OneOf requires at least one choice" in exc.value.errors[0]["message"]


def test_ref_inside_union_type() -> None:
    @monk
    class MultiConfig:
        max_val: int
        val: str | Annotated[int, Interval(gt=0), Interval(lt=Ref("max_val"))]

    validate(MultiConfig(max_val=10, val="a"))
    validate(MultiConfig(max_val=10, val=5))

    with pytest.raises(ValidationError) as exc:
        validate(MultiConfig(max_val=10, val=15))
    assert "Must be less than 10" in exc.value.errors[0]["message"]


def test_validate_arguments_with_refs() -> None:
    def sample_func(max_val: int, vals: Annotated[list[int], Each(Interval(lt=Ref("max_val")))]) -> None:
        pass

    hints = get_type_hints(sample_func, include_extras=True)
    rules = _extract_monk_metadata(hints)

    # Pass
    validate_arguments({"max_val": 10, "vals": [5]}, rules)

    # Fail with nested ValidationError
    with pytest.raises(ValidationError) as exc:
        validate_arguments({"max_val": 10, "vals": [15]}, rules)
    assert "Must be less than 10" in exc.value.errors[0]["message"]
    assert "vals[0]" in exc.value.errors[0]["field"]


def test_validate_arguments_with_refs_direct_error() -> None:
    def sample_func(max_val: int, val: Annotated[int, Interval(lt=Ref("max_val"))]) -> None:
        pass

    hints = get_type_hints(sample_func, include_extras=True)
    rules = _extract_monk_metadata(hints)

    with pytest.raises(ValidationError) as exc:
        validate_arguments({"max_val": 10, "val": 15}, rules)
    assert "Must be less than 10" in exc.value.errors[0]["message"]


def test_validate_dict_with_refs_validation_error() -> None:
    @monk
    class UpdateData:
        max_val: int
        vals: Annotated[list[int], Each(Interval(lt=Ref("max_val")))]

    with pytest.raises(ValidationError) as exc:
        validate_dict({"max_val": 10, "vals": [5, 15]}, UpdateData)

    assert "Must be less than 10" in exc.value.errors[0]["message"]
    assert "vals[1]" in exc.value.errors[0]["field"]


def test_missing_ref_attribute_on_instance() -> None:
    @monk
    class BadRef:
        val: Annotated[int, Eq(Ref("does_not_exist"))]

    with pytest.raises(ValidationError) as exc:
        validate(BadRef(val=10))
    assert "Must be equal to None" in exc.value.errors[0]["message"]
