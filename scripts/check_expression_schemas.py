#!/usr/bin/env python3
"""Isolated JSON Schema conformance for candidate expressive contracts.

Only CI/dev tooling requires jsonschema. The visual runtime has no added deps
and never imports this script for operation or startup.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "contracts"
FIXTURES = ROOT / "examples" / "expressions"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check() -> None:
    names = [
        ("eye-expression.v0.1-candidate.schema.json",
         "meraviglia_curiosa.preview.json"),
        ("cognitive-expression-proposal.v0.1-candidate.schema.json",
         "cognitive-meraviglia.proposal.json"),
    ]
    validators = []
    for schema_file, fixture_file in names:
        schema = load(SCHEMAS / schema_file)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        fixture = load(FIXTURES / fixture_file)
        validator.validate(fixture)
        validators.append(validator)

    expression = load(FIXTURES / names[0][1])
    proposal = load(FIXTURES / names[1][1])
    invalid_expression = [
        {"animation": {**expression["animation"], "blink_interval_ms": 100}},
        {"palette": {**expression["palette"], "ring_brightness_pct": 100}},
        {"eyes": {**expression["eyes"], "left": {**expression["eyes"]["left"], "openness": 5}}},
        {"preview_only": False},
        {"claims_emotion_as_internal_state": True},
        {"script": "exec('something')"},
    ]
    invalid_proposals = [
        {"hardware_execution_authorized": True},
        {"approval_required_for_persistence": False},
        {"presentation": "apply_now"},
        {"source_module": "unknown"},
        {"expression": {**proposal["expression"], "origin": "operator"}},
    ]
    for item in invalid_expression:
        try:
            validators[0].validate({**expression, **item})
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Expression schema accepted invalid patch keys: {tuple(item)}")
    for item in invalid_proposals:
        try:
            validators[1].validate({**proposal, **item})
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Cognitive schema accepted invalid patch keys: {tuple(item)}")
    # The original v0.1 scene schema is frozen; new eye targets live only
    # under an explicit v0.2 profile version.
    v01_schema = load(SCHEMAS / "visual-studio-profile.v0.1-candidate.schema.json")
    v02_schema = load(SCHEMAS / "visual-studio-profile.v0.2-candidate.schema.json")
    Draft202012Validator.check_schema(v01_schema)
    Draft202012Validator.check_schema(v02_schema)
    v01_validator = Draft202012Validator(v01_schema, format_checker=FormatChecker())
    v02_validator = Draft202012Validator(v02_schema, format_checker=FormatChecker())
    old_profile = load(ROOT / "profiles" / "paky01-studio.preview.json")
    new_profile = load(ROOT / "profiles" / "paky02-expressive-studio.preview.json")
    v01_validator.validate(old_profile)
    v02_validator.validate(new_profile)
    for invalid in [
        {**new_profile, "schema_version": "openrgd.visual-studio.profile.v0.1-candidate"},
        {**new_profile, "expressions": {}},
        {**new_profile, "preview_only": False},
    ]:
        if invalid["expressions"] == {}:
            # The reference is then absent from the catalog, which the
            # Python engine rejects. Validate this invariant separately.
            from rgd_visual.studio import validate_profile
            try:
                validate_profile(invalid)
            except ValueError:
                continue
            raise AssertionError("Engine accepted missing eye expression ref")
        try:
            v02_validator.validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("v0.2 schema accepted wrong version or permissions")
    print("EXPRESSIVE CONTRACTS: 4 positive fixtures + 14 negative checks OK")


if __name__ == "__main__":
    check()
