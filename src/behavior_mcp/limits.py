"""Closed trusted operational restrictions; these never change Behavior definitions."""

import json
from dataclasses import dataclass
from typing import Any

from .schemas import JSON, OperationError

DEFAULT_PROFILES = {
    "default": {"rlimit": 20_000_000, "wall_clock_guard_ms": 60_000},
    "bounded": {"rlimit": 20_000, "wall_clock_guard_ms": 5_000},
}


@dataclass(frozen=True)
class HostLimits:
    frame_bytes: int = 1048576
    nesting_depth: int = 32
    page_default: int = 50
    page_max: int = 100
    verification_workers: int = 2
    _profiles_json: str = json.dumps(DEFAULT_PROFILES, sort_keys=True)

    @staticmethod
    def from_document(value: Any = None) -> "HostLimits":
        def invalid() -> None:
            raise OperationError(
                "invalid_input", "HOST_LIMITS_INVALID", "Invalid trusted host limits"
            )

        doc = {} if value is None else value
        maxima = {
            "frame_bytes": 1048576,
            "nesting_depth": 32,
            "page_default": 50,
            "page_max": 100,
            "verification_workers": 2,
        }
        if not isinstance(doc, dict) or set(doc) - (
            set(maxima) | {"verification_profiles"}
        ):
            invalid()
        for name, maximum in maxima.items():
            if name in doc and (
                type(doc[name]) is not int or not 1 <= doc[name] <= maximum
            ):
                invalid()
        page_max = doc.get("page_max", 100)
        page_default = doc.get("page_default", min(50, page_max))
        if page_default > page_max:
            invalid()
        profiles = json.loads(json.dumps(DEFAULT_PROFILES))
        overrides = doc.get("verification_profiles", {})
        if not isinstance(overrides, dict) or set(overrides) - set(profiles):
            invalid()
        for name, parameters in overrides.items():
            if not isinstance(parameters, dict) or set(parameters) - set(
                profiles[name]
            ):
                invalid()
            for key, budget in parameters.items():
                if type(budget) is not int or not 1 <= budget <= profiles[name][key]:
                    invalid()
                profiles[name][key] = budget
        return HostLimits(
            frame_bytes=doc.get("frame_bytes", 1048576),
            nesting_depth=doc.get("nesting_depth", 32),
            page_default=page_default,
            page_max=page_max,
            verification_workers=doc.get("verification_workers", 2),
            _profiles_json=json.dumps(profiles, sort_keys=True),
        )

    def profile(self, profile_id: str) -> JSON:
        profiles = json.loads(self._profiles_json)
        if profile_id not in profiles:
            raise OperationError(
                "unsupported",
                "VERIFICATION_PROFILE_UNSUPPORTED",
                "Verification profile is not host-enabled",
            )
        return dict(profiles[profile_id])
