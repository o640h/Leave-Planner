"""Argon2id password hashing at the approved application boundary."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.low_level import Type

MINIMUM_PASSWORD_LENGTH = 10

password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

# Public dummy material equalises the expensive verification path for unknown email accounts.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$Qyt7AdIPvBXl4fQABaPr8A$"
    "vFXPjq5bpdDwsvsrWywsPcJUpPnaupqbpwtgp/FDxKI"
)


def validate_new_password(password: str) -> None:
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(f"The password must contain at least {MINIMUM_PASSWORD_LENGTH} characters")


def hash_password(password: str) -> str:
    validate_new_password(password)
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except InvalidHashError, VerificationError:
        return False
