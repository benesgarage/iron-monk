from typing import Annotated, TypedDict
from monk import monk, validate, validate_dict
from monk.constraints import Email, HexColor, Interval, Trimmed, URL, Nullable


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
            search_term: Annotated[str | None, Nullable, Trimmed] = None,
        ) -> str:
            return f"Found {limit} products"

    schema = strawberry.Schema(query=Query)

    # A resolver wrapped in @monk perfectly catches argument validation directly
    res_bad = schema.execute_sync("query { searchProducts(limit: 200) }")
    assert res_bad.errors is not None
    assert "Validation failed" in str(res_bad.errors[0].original_error)
