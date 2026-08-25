from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_FORBIDDEN_FIELDS = frozenset(
    {
        "api_key", "token", "secret", "password", "endpoint", "model_url",
        "base_url", "credentials",
    }
)


class ScopeLimits(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    max_files: int = Field(strict=True, gt=0)
    max_bytes: int = Field(strict=True, gt=0)


class WorkerProfiles(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    extraction_profile: str = Field(min_length=1)
    validation_profile: str | None = None


class KnowledgeConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always"
    )

    schema_version: Literal["0.1"] = "0.1"
    repository_provider: Literal["local-git"] = "local-git"
    evidence_provider: Literal["codewiki"] = "codewiki"
    language: Literal["zh", "en"] = "zh"
    worker_profiles: WorkerProfiles
    exclusions: tuple[str, ...] = ()
    scope_limits: ScopeLimits
    default_context_budget: int = Field(strict=True, gt=0)

    @field_validator("exclusions")
    @classmethod
    def validate_exclusions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for pattern in value:
            parsed = PurePosixPath(pattern)
            if (
                not pattern
                or parsed.is_absolute()
                or ".." in parsed.parts
                or "\\" in pattern
                or pattern.startswith("/")
            ):
                raise ValueError(f"unsafe exclusion pattern: {pattern}")
        return tuple(sorted(set(value)))


def _reject_forbidden_extras(data: dict) -> None:
    for key in data:
        if key in _FORBIDDEN_FIELDS:
            raise ValueError(
                f"secret/credential field is forbidden in repository config: {key}"
            )


def load_config(path: str | Path) -> KnowledgeConfig:
    file = Path(path)
    try:
        payload = yaml.safe_load(file.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ValueError(f"config is unreadable: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("config must contain a mapping")
    _reject_forbidden_extras(payload)
    try:
        return KnowledgeConfig.model_validate(payload)
    except ValueError as error:
        rendered = str(error)
        if "Extra inputs are not permitted" in rendered:
            raise ValueError("unknown key or invalid config: " + rendered) from error
        raise


def write_config(path: str | Path, config: KnowledgeConfig) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        yaml.safe_dump(
            config.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


__all__ = [
    "KnowledgeConfig",
    "ScopeLimits",
    "WorkerProfiles",
    "load_config",
    "write_config",
]
