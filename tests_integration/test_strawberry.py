from typing import Annotated, TypedDict
from monk import monk, validate, validate_dict
from monk.constraints import Email, HexColor, Interval, Trimmed, URL


def test_strawberry_input_validation() -> None:
    import strawberry

    @strawberry.input
    @monk
    class RegisterInput:
        email: Annotated[str, Email]

    @strawberry.type
    class Query:
        @strawberry.field
        def check_email(self, input: RegisterInput) -> str:
            valid = validate(input)
            return valid.email

    schema = strawberry.Schema(query=Query)

    res1 = schema.execute_sync('query { checkEmail(input: {email: "test@domain.com"}) }')
    assert res1.errors is None
    assert res1.data == {"checkEmail": "test@domain.com"}

    res2 = schema.execute_sync('query { checkEmail(input: {email: "bad"}) }')
    assert res2.errors is not None
    assert "Validation failed" in str(res2.errors[0].original_error)


def test_strawberry_custom_scalars() -> None:
    import strawberry
    from strawberry.schema.config import StrawberryConfig
    from typing import NewType

    HexColorType = NewType("HexColorType", str)

    def parse_hex(value: str) -> HexColorType:
        HexColor().validate(value)
        return HexColorType(value)

    @strawberry.type
    class Query:
        @strawberry.field
        def check_color(self, color: HexColorType) -> str:
            return f"Color is {color}"

    schema = strawberry.Schema(
        query=Query,
        config=StrawberryConfig(scalar_map={HexColorType: strawberry.scalar(name="HexColor", parse_value=parse_hex)}),
    )

    res1 = schema.execute_sync('query { checkColor(color: "#FFF") }')
    assert res1.errors is None
    assert res1.data == {"checkColor": "Color is #FFF"}

    res2 = schema.execute_sync('query { checkColor(color: "bad-color") }')
    assert res2.errors is not None


def test_strawberry_defensive_egress() -> None:
    import strawberry

    class LegacyUserDict(TypedDict):
        email: Annotated[str, Email]
        website: Annotated[str, URL]

    @strawberry.type
    class User:
        email: str
        website: str

    @strawberry.type
    class Query:
        @strawberry.field
        def fetch_legacy_user(self) -> User:
            raw_payload = {"email": "john@domain.com", "website": "https://example.com", "is_admin": True}
            safe_data = validate_dict(raw_payload, LegacyUserDict, drop_extra_keys=True)
            return User(**safe_data)

    schema = strawberry.Schema(query=Query)
    res = schema.execute_sync("query { fetchLegacyUser { email website } }")
    assert res.errors is None
    assert res.data == {"fetchLegacyUser": {"email": "john@domain.com", "website": "https://example.com"}}


def test_strawberry_argument_validation() -> None:
    import strawberry

    @strawberry.type
    class Query:
        @strawberry.field
        @monk
        def search_products(
            self,
            limit: Annotated[int, Interval(gt=0, le=100)] = 20,
            search_term: Annotated[str, Trimmed] | None = None,
        ) -> str:
            return f"Found {limit} products"

    schema = strawberry.Schema(query=Query)

    # A resolver wrapped in @monk perfectly catches argument validation directly
    res_bad = schema.execute_sync("query { searchProducts(limit: 200) }")
    assert res_bad.errors is not None
    assert "Validation failed" in str(res_bad.errors[0].original_error)


def test_strawberry_unset_sentinel() -> None:
    import strawberry
    from monk import settings

    # Tell iron-monk to completely ignore Strawberry's omitted-field runtime sentinel
    settings.ignored_sentinels = (strawberry.UNSET,)

    @strawberry.input
    @monk
    class PatchInput:
        # Resolves as Union[str, None, UNSET] under the hood, perfectly preserving your annotations
        email: strawberry.Maybe[Annotated[str, Email]] = strawberry.UNSET

    @strawberry.type
    class Query:
        @strawberry.field
        def patch_user_sentinel(self, input: PatchInput) -> str:
            valid = validate(input)
            if valid.email is strawberry.UNSET:
                return "Omitted"
            return str(valid.email)

    schema = strawberry.Schema(query=Query)

    # 1. Field omitted (UNSET is preserved and validation is safely skipped)
    res1 = schema.execute_sync("query { patchUserSentinel(input: {}) }")
    assert res1.errors is None
    assert res1.data == {"patchUserSentinel": "Omitted"}

    # 2. Field provided but invalid (Validation is strictly enforced)
    res2 = schema.execute_sync('query { patchUserSentinel(input: {email: "bad"}) }')
    assert res2.errors is not None

    settings.ignored_sentinels = ()  # Cleanup


def test_strawberry_value_unwrappers() -> None:
    import strawberry
    from strawberry.types.maybe import Some
    from monk import settings

    # Teach iron-monk how to extract values from Strawberry's Some wrappers
    settings.unwrappers = {Some: lambda x: x.value}

    @strawberry.input
    @monk
    class UpdateInput:
        email: strawberry.Maybe[Annotated[str, Email]]

    @strawberry.type
    class Query:
        @strawberry.field
        def check_update(self, input: UpdateInput) -> str:
            valid = validate(input)
            if isinstance(valid.email, Some):
                return valid.email.value
            return str(valid.email)

    schema = strawberry.Schema(query=Query)

    res1 = schema.execute_sync('query { checkUpdate(input: {email: "test@domain.com"}) }')
    assert res1.errors is None
    assert res1.data == {"checkUpdate": "test@domain.com"}

    res2 = schema.execute_sync('query { checkUpdate(input: {email: "bad"}) }')
    assert res2.errors is not None
    assert "Validation failed" in str(res2.errors[0].original_error)

    settings.unwrappers = {}  # Cleanup


def test_strawberry_one_of_input() -> None:
    import strawberry
    from strawberry.types.maybe import Some
    from typing import Any
    from monk import settings

    settings.unwrappers = {Some: lambda x: x.value}

    # Simulate a user's custom stacked decorator where Strawberry builds the dataclass first
    def monk_input(**kwargs: Any) -> Any:
        def wrapper(c: type) -> type:
            return monk(strawberry.input(**kwargs)(c))

        return wrapper

    @monk_input(one_of=True)
    class DCROneOfEntityInput:
        hcp: strawberry.Maybe[str]
        hco: strawberry.Maybe[str]

    @strawberry.type
    class Query:
        @strawberry.field
        def check_one_of(self, input: DCROneOfEntityInput) -> str:
            validate(input)
            return "Valid OneOf!"

    schema = strawberry.Schema(query=Query)

    # 1. Provide exactly one (Strawberry validation passes, Monk validation passes)
    res1 = schema.execute_sync('query { checkOneOf(input: {hcp: "value"}) }')
    assert res1.errors is None

    # 2. Provide multiple (Strawberry's __post_init__ catches it)
    res2 = schema.execute_sync('query { checkOneOf(input: {hcp: "value", hco: "value2"}) }')
    assert res2.errors is not None
    assert "exactly one" in str(res2.errors[0].message)

    settings.ignored_sentinels = ()  # Cleanup


def test_strawberry_comprehensive_maybe_patch() -> None:
    """Thoroughly tests the interaction of UNSET sentinels, Some wrappers, Nullability, and specific error bubbling."""
    import strawberry
    from monk import settings
    from monk.constraints import Each, LowerCase, Nullable

    settings.type_metadata = {strawberry.Maybe: [Nullable]}

    @monk
    @strawberry.input
    class ComprehensivePatchInput:
        email: strawberry.Maybe[Annotated[str, Email]]
        bio: strawberry.Maybe[Annotated[str, Trimmed] | None]
        tags: strawberry.Maybe[Annotated[list[str], Each(LowerCase)]]

    @strawberry.type
    class Query:
        @strawberry.field
        def patch_profile(self, input: ComprehensivePatchInput) -> str:
            validate(input)
            return "SUCCESS"

    schema = strawberry.Schema(query=Query)

    # 1. All omitted (Safely bypasses all constraints)
    res1 = schema.execute_sync("query { patchProfile(input: {}) }")
    assert res1.errors is None

    # 2. Valid Email (Successfully unwraps Some and checks Email)
    res2 = schema.execute_sync('query { patchProfile(input: {email: "kai@monk.com"}) }')
    assert res2.errors is None

    # 3. Nullable Maybe explicitly set to null (Bypasses Trimmed constraint natively)
    res3 = schema.execute_sync("query { patchProfile(input: {bio: null}) }")
    assert res3.errors is None

    # 4. Invalid Email (Bubbles specific 'Email' error instead of generic Union error)
    res4 = schema.execute_sync('query { patchProfile(input: {email: "bad-email"}) }')
    assert res4.errors is not None
    assert "email" in str(res4.errors[0].original_error)

    # 5. Invalid Bio (Bubbles specific 'Trimmed' error)
    res5 = schema.execute_sync('query { patchProfile(input: {bio: " untrimmed "}) }')
    assert res5.errors is not None
    assert "whitespace" in str(res5.errors[0].original_error)

    # 6. Invalid Tags List (Recursively bubbles the 'LowerCase' error inside the list index!)
    res6 = schema.execute_sync('query { patchProfile(input: {tags: ["valid", "INVALID"]}) }')
    assert res6.errors is not None
    assert "islower" in str(res6.errors[0].original_error)

    settings.type_metadata = {}
