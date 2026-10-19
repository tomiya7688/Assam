"""Profile marker carried by JSON ASSAM programs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramProfile:
    name: str
    version: str
    registry_schema_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("profile name must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("profile version must be a non-empty string")
        if type(self.registry_schema_version) is not int or self.registry_schema_version < 1:
            raise ValueError("registry schema version must be a positive integer")

    def to_dict(self) -> dict[str, str | int]:
        return {
            "name": self.name,
            "version": self.version,
            "registry_schema_version": self.registry_schema_version,
        }

    @classmethod
    def from_dict(cls, value: dict) -> ProgramProfile:
        if not isinstance(value, dict) or set(value) != {"name", "version", "registry_schema_version"}:
            raise ValueError("program profile must contain name, version, and registry_schema_version")
        return cls(value["name"], value["version"], value["registry_schema_version"])
