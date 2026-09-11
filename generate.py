"""Deterministic synthetic release-policy cases used by the raw data builder."""

from __future__ import annotations

from pathlib import Path
import hashlib
import hmac
import os
import random


CASE_COUNT = 900
FAMILY_COUNT = 45
COMPONENT_COUNT = 22
ENVIRONMENT_COUNT = 6
HISTORICAL_PROBE_COUNT = 96
COUNTERFACTUAL_COUNT = 64


def load_secret(secret: bytes | None = None) -> bytes:
    """Return the generation secret. It is never published; without it the data cannot be reproduced."""
    if secret is not None:
        return secret
    value = os.environ.get("MRCR_SECRET")
    path = os.environ.get("MRCR_SECRET_FILE")
    if value is None and path:
        value = Path(path).read_text(encoding="utf-8").strip()
    if not value or len(value) < 32:
        raise RuntimeError("set MRCR_SECRET or MRCR_SECRET_FILE to the withheld generation secret (>= 32 hex chars)")
    return bytes.fromhex(value)


def _digest(secret: bytes, label: str) -> bytes:
    return hmac.new(secret, label.encode("utf-8"), hashlib.sha256).digest()


def _opaque(secret: bytes, label: str, length: int) -> str:
    return _digest(secret, label).hex()[:length]


def _pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _active_rules(answer: dict, environment_id: str, enabled_components: set[str]) -> set[tuple]:
    """Return the hidden rules violated by a configuration."""
    active: set[tuple] = set()
    for left, right in answer["requires"]:
        if left in enabled_components and right not in enabled_components:
            active.add(("requires", left, right))
    for left, right in answer["conflicts"]:
        if left in enabled_components and right in enabled_components:
            active.add(("conflicts", left, right))
    for gate in answer["gates"]:
        if gate["environment_id"] != environment_id:
            continue
        left, right = gate["left"], gate["right"]
        if gate["relation"] == "requires" and left in enabled_components and right not in enabled_components:
            active.add(("gate_requires", environment_id, left, right))
        if gate["relation"] == "conflicts" and left in enabled_components and right in enabled_components:
            active.add(("gate_conflicts", environment_id, left, right))
    return active


def evaluate(answer: dict, environment_id: str, enabled_components: list[str] | set[str]) -> int:
    """Return the deterministic release outcome: one for pass and zero for fail."""
    return int(not _active_rules(answer, environment_id, set(enabled_components)))


def _make_answer(rng: random.Random, components: list[str], environments: list[str]) -> dict:
    order = components[:]
    rng.shuffle(order)
    requires_candidates = [(order[i], order[j]) for i in range(1, len(order)) for j in range(i)]
    rng.shuffle(requires_candidates)
    requires = requires_candidates[: rng.randint(14, 20)]
    used_pairs = {_pair(left, right) for left, right in requires}
    conflict_candidates = [
        _pair(left, right)
        for index, left in enumerate(components)
        for right in components[index + 1 :]
        if _pair(left, right) not in used_pairs
    ]
    rng.shuffle(conflict_candidates)
    conflicts = conflict_candidates[: rng.randint(6, 10)]
    global_rules = {("requires", left, right) for left, right in requires}
    global_rules.update(("conflicts", left, right) for left, right in conflicts)
    gate_candidates = []
    for left_index, left in enumerate(order):
        for right in order[:left_index]:
            if ("requires", left, right) not in global_rules:
                gate_candidates.append(("requires", left, right))
    for index, left in enumerate(components):
        for right in components[index + 1 :]:
            if ("conflicts", left, right) not in global_rules:
                gate_candidates.append(("conflicts", left, right))
    gate_keys = set()
    while len(gate_keys) < rng.randint(8, 12):
        relation, left, right = rng.choice(gate_candidates)
        gate_keys.add((rng.choice(environments), relation, left, right))
    gates = [
        {"environment_id": environment, "relation": relation, "left": left, "right": right}
        for environment, relation, left, right in sorted(gate_keys)
    ]
    return {
        "requires": sorted([list(pair) for pair in requires]),
        "conflicts": sorted([list(pair) for pair in conflicts]),
        "gates": gates,
    }


def _passing_components(rng: random.Random, answer: dict, components: list[str], environment_id: str) -> list[str]:
    """Sample a nonempty passing configuration by repairing requirements and conflicts."""
    for _ in range(400):
        enabled = {component for component in components if rng.random() < 0.38}
        if not enabled:
            enabled.add(rng.choice(components))
        for _ in range(len(components) + 2):
            changed = False
            for left, right in answer["requires"]:
                if left in enabled and right not in enabled:
                    enabled.add(right)
                    changed = True
            for gate in answer["gates"]:
                if gate["environment_id"] == environment_id and gate["relation"] == "requires":
                    if gate["left"] in enabled and gate["right"] not in enabled:
                        enabled.add(gate["right"])
                        changed = True
            if not changed:
                break
        for left, right in answer["conflicts"]:
            if left in enabled and right in enabled:
                enabled.remove(rng.choice((left, right)))
        for gate in answer["gates"]:
            if gate["environment_id"] == environment_id and gate["relation"] == "conflicts":
                if gate["left"] in enabled and gate["right"] in enabled:
                    enabled.remove(rng.choice((gate["left"], gate["right"])))
        if enabled and evaluate(answer, environment_id, enabled):
            return sorted(enabled)
    for component in components:
        if evaluate(answer, environment_id, [component]):
            return [component]
    raise RuntimeError("could not construct a passing configuration")


def _rule_token(secret: bytes, case_number: int, rule: tuple) -> str:
    """Return a case-specific opaque signature keyed by the withheld secret."""
    code = int.from_bytes(_digest(secret, f"diag:{case_number}:" + "|".join(rule))[:4], "big") % 127
    return f"diag_{code:03d}"


def _trace(rng: random.Random, secret: bytes, case_number: int, active_rules: set[tuple]) -> list[str]:
    """Generate noisy opaque diagnostics with one repeatable latent signature."""
    tokens = [f"diag_{rng.randrange(127):03d}" for _ in range(1 + rng.randrange(3))]
    if active_rules and rng.random() < 0.75:
        tokens.append(_rule_token(secret, case_number, rng.choice(sorted(active_rules))))
    return sorted(set(tokens))


def _probe(rng: random.Random, secret: bytes, case_number: int, answer: dict, components: list[str], environments: list[str], probe_id: str, must_fail: bool) -> dict:
    environment_id = rng.choice(environments)
    if not must_fail:
        enabled = _passing_components(rng, answer, components, environment_id)
    else:
        for _ in range(400):
            enabled = [component for component in components if rng.random() < 0.55]
            if enabled and not evaluate(answer, environment_id, enabled):
                break
        else:
            raise RuntimeError("could not construct a failing configuration")
    active = _active_rules(answer, environment_id, set(enabled))
    return {
        "probe_id": probe_id,
        "environment_id": environment_id,
        "enabled_components": sorted(enabled),
        "outcome": int(not active),
        "failure_trace": _trace(rng, secret, case_number, active),
    }


def _rule_witness(rng: random.Random, answer: dict, components: list[str], rule: tuple) -> tuple[str, list[str]]:
    """Create a locally informative probe from an otherwise passing configuration."""
    kind = rule[0]
    if kind == "requires":
        _, left, right = rule
        environment_id = rng.choice([f"env_{index:02d}" for index in range(ENVIRONMENT_COUNT)])
        enabled = set(_passing_components(rng, answer, components, environment_id))
        enabled.add(left)
        enabled.discard(right)
        return environment_id, sorted(enabled)
    if kind == "conflicts":
        _, left, right = rule
        environment_id = rng.choice([f"env_{index:02d}" for index in range(ENVIRONMENT_COUNT)])
        enabled = set(_passing_components(rng, answer, components, environment_id))
        enabled.update((left, right))
        return environment_id, sorted(enabled)
    _, environment_id, left, right = rule
    enabled = set(_passing_components(rng, answer, components, environment_id))
    if kind == "gate_requires":
        enabled.add(left)
        enabled.discard(right)
    else:
        enabled.add(left)
        enabled.add(right)
    return environment_id, sorted(enabled)


def generate_case(case_number: int, secret: bytes | None = None) -> dict:
    """Generate one independent anonymized release-policy reconstruction case.

    Every random draw, identifier and diagnostic token is derived from the withheld
    secret, so the public code cannot reproduce released data without it."""
    if not 0 <= case_number < CASE_COUNT:
        raise ValueError(f"case_number must be in [0, {CASE_COUNT - 1}]")
    secret = load_secret(secret)
    rng = random.Random(int.from_bytes(_digest(secret, f"case:{case_number}")[:16], "big"))
    components = [f"cmp_{index:02d}" for index in range(COMPONENT_COUNT)]
    environments = [f"env_{index:02d}" for index in range(ENVIRONMENT_COUNT)]
    answer = _make_answer(rng, components, environments)
    active_rules = []
    active_rules.extend(("requires", left, right) for left, right in answer["requires"])
    active_rules.extend(("conflicts", left, right) for left, right in answer["conflicts"])
    for gate in answer["gates"]:
        active_rules.append((f"gate_{gate['relation']}", gate["environment_id"], gate["left"], gate["right"]))

    probes = []
    for rule in active_rules:
        for _ in range(2):
            environment_id, enabled = _rule_witness(rng, answer, components, rule)
            active = _active_rules(answer, environment_id, set(enabled))
            probes.append(
                {
                    "probe_id": "probe_" + _opaque(secret, f"probe:{case_number}:{len(probes)}", 8),
                    "environment_id": environment_id,
                    "enabled_components": enabled,
                    "outcome": int(not active),
                    "failure_trace": _trace(rng, secret, case_number, {rule}),
                }
            )
    while len(probes) < HISTORICAL_PROBE_COUNT:
        probes.append(_probe(rng, secret, case_number, answer, components, environments, "probe_" + _opaque(secret, f"probe:{case_number}:{len(probes)}", 8), len(probes) % 2 == 0))
    probes = probes[:HISTORICAL_PROBE_COUNT]

    counterfactuals = []
    for index in range(COUNTERFACTUAL_COUNT):
        probe = _probe(rng, secret, case_number, answer, components, environments, f"cf_{index:03d}", index % 2 == 1)
        counterfactuals.append(
            {
                "environment_id": probe["environment_id"],
                "enabled_components": probe["enabled_components"],
                "outcome": probe["outcome"],
            }
        )
    rng.shuffle(probes)
    return {
        "case_id": "case_" + _opaque(secret, f"case_id:{case_number}", 10),
        "family_id": "family_" + _opaque(secret, f"family:{case_number % FAMILY_COUNT}", 6),
        "component_ids": components,
        "environment_ids": environments,
        "answer": answer,
        "probes": probes,
        "counterfactuals": counterfactuals,
    }
