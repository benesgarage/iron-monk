import pytest
from typing import Annotated
from monk import monk, validate
from monk.exceptions import ValidationError, UnvalidatedAccessError
from monk.constraints import Email, Match, LowerCase


@monk
class Address:
    zip_code: Annotated[str, Match(r"^\d{5}$")]


@monk
class User:
    email: Annotated[str, Email]
    address: Address
    past_addresses: list[Address]


def test_nested_models_success():
    user = User(
        email="test@domain.com",
        address=Address(zip_code="12345"),
        past_addresses=[
            Address(zip_code="54321"),
            Address(zip_code="98765")
        ]
    )
    
    # Prove that the parent AND all the children start guarded/unvalidated!
    with pytest.raises(UnvalidatedAccessError):
        _ = user.email
    with pytest.raises(UnvalidatedAccessError):
        _ = user.address.zip_code
    with pytest.raises(UnvalidatedAccessError):
        _ = user.past_addresses[0].zip_code
        
    validated_user = validate(user)
    
    # Accessing fields should no longer raise an exception
    assert validated_user.email == "test@domain.com"
    assert validated_user.address.zip_code == "12345"
    assert validated_user.past_addresses[0].zip_code == "54321"
    assert validated_user.past_addresses[1].zip_code == "98765"


def test_nested_models_failure():
    user = User(
        email="bad-email",
        address=Address(zip_code="123"),
        past_addresses=[
            Address(zip_code="54321"),
            Address(zip_code="abcde")
        ]
    )
    
    with pytest.raises(ValidationError) as exc:
        validate(user)
        
    errors = exc.value.errors
    assert len(errors) == 3
    
    # Verify that the recursion accurately prefixed the field paths
    assert errors[0]["field"] == "email"
    assert errors[1]["field"] == "address.zip_code"
    assert errors[2]["field"] == "past_addresses[1].zip_code"


# --- Deep Nesting and Optionality Tests ---

@monk
class Config:
    environment: Annotated[str, LowerCase]


@monk
class Server:
    config: Config | None = None
    backup_config: Config | None = None


@monk
class Cluster:
    primary: Server
    secondaries: list[Server]
    matrix_nodes: list[list[Server]] | None = None
    server_map: dict[str, Server] | None = None


def test_deep_nested_paths_and_optional_models():
    cluster = Cluster(
        primary=Server(
            config=Config(environment="PROD"),  # Fails LowerCase
            backup_config=None                  # Prove recursion doesn't crash on None
        ),
        secondaries=[
            Server(config=Config(environment="dev")),     # Passes
            Server(config=Config(environment="STAGING"))  # Fails LowerCase
        ],
        matrix_nodes=[
            [Server(config=Config(environment="TEST"))]   # Fails LowerCase
        ],
        server_map={
            "eu-west": Server(config=Config(environment="PROD")) # Fails LowerCase
        }
    )
    
    with pytest.raises(ValidationError) as e:
        validate(cluster)
        
    errors = e.value.errors
    assert len(errors) == 4
    
    # Prove the path builder works dynamically for n-levels deep
    assert errors[0]["field"] == "primary.config.environment"
    assert errors[1]["field"] == "secondaries[1].config.environment"
    assert errors[2]["field"] == "matrix_nodes[0][0].config.environment"
    assert errors[3]["field"] == "server_map['eu-west'].config.environment"


def test_optional_nested_models_success():
    cluster = Cluster(
        primary=Server(config=None, backup_config=None),
        secondaries=[]
    )
    
    validated = validate(cluster)
    
    # Prove that everything is accessible even when sparse
    assert validated.primary.config is None
    assert validated.secondaries == []