"""
Very simple "user partitioning" system used to shed load quickly from ingestion
pipeline if things go wrong. Allows for conditions based on project ID, event
type and organization ID.

This is similar to existing featureflagging systems we have, but with less
features and more performant.
"""

import copy
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from sentry import options
from sentry.utils import metrics

Condition = Dict[str, str]
KillswitchConfig = List[Condition]
LegacyKillswitchConfig = Union[KillswitchConfig, List[int]]
Context = Dict[str, Any]


@dataclass
class KillswitchInfo:
    description: str
    fields: Dict[str, str]


ALL_KILLSWITCH_OPTIONS = {
    "store.load-shed-group-creation-projects": KillswitchInfo(  # type: ignore
        description="Drop event in save_event before entering transaction to create group",
        fields={
            "project_id": "A project ID to filter events by.",
            "platform": "The event platform as defined in the event payload's platform field.",
        },
    ),
    "store.load-shed-pipeline-projects": KillswitchInfo(  # type: ignore
        description="Drop event in ingest consumer. Available fields are severely restricted because nothing is parsed yet.",
        fields={
            "project_id": "A project ID to filter events by.",
            "event_id": "An event ID as given in the event payload.",
            "has_attachments": "Filter events by whether they have been sent together with attachments or not. Note that attachments can be sent completely separately as well.",
        },
    ),
    "store.load-shed-parsed-pipeline-projects": KillswitchInfo(  # type: ignore
        description="Drop events in ingest consumer after parsing them. Available fields are more but a bunch of stuff can go wrong before that.",
        fields={
            "organization_id": "Numeric organization ID to filter events by.",
            "project_id": "A project ID to filter events by.",
            "event_type": "transaction, csp, hpkp, expectct, expectstaple, transaction, default or null",
            "has_attachments": "Filter events by whether they have been sent together with attachments or not. Note that attachments can be sent completely separately as well.",
            "event_id": "An event ID as given in the event payload.",
        },
    ),
    "store.load-shed-process-event-projects": KillswitchInfo(  # type: ignore
        description="Drop events in process_event.",
        fields={
            "project_id": "A project ID to filter events by.",
            "event_id": "An event ID as given in the event payload.",
            "platform": "The event platform as defined in the event payload's platform field.",
        },
    ),
    "store.load-shed-symbolicate-event-projects": KillswitchInfo(  # type: ignore
        description="Drop events in symbolicate_event.",
        fields={
            "project_id": "A project ID to filter events by.",
            "event_id": "An event ID as given in the event payload.",
            "platform": "The event platform as defined in the event payload's platform field.",
        },
    ),
}


def validate_user_input(killswitch_name: str, option_value: Any) -> KillswitchConfig:
    return normalize_value(killswitch_name, option_value, strict=True)


def normalize_value(
    killswitch_name: str, option_value: Any, strict: bool = False
) -> KillswitchConfig:
    rv = []
    for condition in option_value or ():
        if not condition:
            continue
        elif isinstance(condition, int):
            rv.append({"project_id": str(condition)})
        elif isinstance(condition, dict):
            for k in ALL_KILLSWITCH_OPTIONS[killswitch_name].fields:
                if k not in condition:
                    if strict:
                        raise ValueError(f"Missing field {k}")
                    else:
                        condition[k] = None

            if strict:
                for k in list(condition):
                    if k not in ALL_KILLSWITCH_OPTIONS[killswitch_name].fields:
                        raise ValueError(f"Unknown field: {k}")

            if any(v is not None for v in condition.values()):
                rv.append(condition)

    return rv


def killswitch_matches_context(killswitch_name: str, context: Context) -> bool:
    assert killswitch_name in ALL_KILLSWITCH_OPTIONS
    assert set(ALL_KILLSWITCH_OPTIONS[killswitch_name].fields) == set(context)
    option_value = options.get(killswitch_name)
    rv = _value_matches(killswitch_name, option_value, context)
    metrics.incr(
        "sentry.killswitches.run",
        tags={"killswitch_name": killswitch_name, "decision": "matched" if rv else "passed"},
    )

    return rv


def _value_matches(
    killswitch_name: str, raw_option_value: LegacyKillswitchConfig, context: Context
) -> bool:
    option_value = normalize_value(killswitch_name, raw_option_value)

    for condition in option_value:
        for field, matching_value in condition.items():
            value = context.get(field)
            if value is None:
                break

            if str(value) != matching_value:
                break
        else:
            return True

    return False


def print_conditions(killswitch_name: str, raw_option_value: LegacyKillswitchConfig) -> str:
    option_value = normalize_value(killswitch_name, raw_option_value)

    if not option_value:
        return "<disabled entirely>"

    return "DROP DATA WHERE\n  " + " OR\n  ".join(
        "("
        + " AND ".join(
            f"{field} = {matching_value}"
            for field, matching_value in condition.items()
            if matching_value is not None
        )
        + ")"
        for condition in option_value
    )


def add_condition(
    killswitch_name: str, raw_option_value: LegacyKillswitchConfig, condition: Condition
) -> KillswitchConfig:
    option_value = copy.deepcopy(normalize_value(killswitch_name, raw_option_value))
    option_value.append(condition)
    return normalize_value(killswitch_name, option_value)


def remove_condition(
    killswitch_name: str, raw_option_value: LegacyKillswitchConfig, condition: Condition
) -> KillswitchConfig:
    option_value = copy.deepcopy(normalize_value(killswitch_name, raw_option_value))
    option_value = [m for m in option_value if m != condition]
    return normalize_value(killswitch_name, option_value)
