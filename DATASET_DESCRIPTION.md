# Masked Release-Constraint Reconstruction Dataset

## Overview

This is an original, fully synthetic dataset for reconstructing hidden release-control policies from anonymized deployment probes. A release-control policy decides whether an enabled set of components may run in an environment. Each policy contains directed dependencies, mutually incompatible component pairs, and environment-specific rules. No production repository, user data, customer data, or third-party dataset is used.

Version 2 (2026-09-06) replaces the first release entirely. The first release could be regenerated from the public generator code because its seed was published and its case identifiers encoded the generator index; every identifier, random draw and diagnostic token in version 2 is derived from a secret that is not published, and no version-1 case survives. Version 3 (2026-09-11) raises the historical probes per case from 96 to 192; the cases, identifiers and split are unchanged.

The raw upload contains 900 independent cases in 45 grouping families of 20 cases each. Every case has 22 anonymous components (`cmp_00` to `cmp_21`), six anonymous environments (`env_00` to `env_05`), 192 historical probes, and 64 private counterfactual probes. There are 172,800 historical probe rows in total.

## Release At A Glance

| Item | Value |
|---|---:|
| Raw files | 9 |
| Cases | 900 |
| Families (grouping keys) | 45, 20 cases each |
| Components per case | 22 |
| Environments per case | 6 |
| Historical probes per case | 192 |
| Private counterfactual probes per case | 64 |
| Prepared split | 36 families / 720 training cases, 9 families / 180 test cases |
| Data origin | Creator-generated synthetic data, version 3 |

## Raw File Structure

The uploaded ZIP is flat and contains exactly these nine files at its root:

| File | Contents |
|---|---|
| `probes.csv` | 172,800 historical probe records, the primary observation table |
| `labels.csv` | one creator-side record per case: the hidden policy, the inventories, and the private counterfactual probes; used by `prepare.py` and never copied into public prepared data |
| `case_index.csv` | one record per case: `case_id` and its family key |
| `source_metadata.json` | provenance, scale, seed policy and license metadata |
| `LICENSE` | CC BY 4.0 notice and license URL |
| `ATTRIBUTION.txt` | attribution text |
| `DATASET_CARD.md` | short scope and safety summary |
| `DATASET_DESCRIPTION.md` | this document |
| `PACKAGE_MANIFEST.sha256` | SHA-256 checksum of every other raw file |

## Columns

`probes.csv`

| Column | Type | Description |
|---|---|---|
| `case_id` | string | Opaque identifier of one independent release-policy system, a keyed hash |
| `family_id` | string | Opaque grouping key used only to build family-held-out splits |
| `probe_id` | string | Opaque probe identifier, unique within a case |
| `environment_id` | string | The environment in which the enabled set was evaluated |
| `enabled_components_json` | JSON string array | Sorted, nonempty array of enabled component IDs |
| `outcome` | integer | `1` if the probe passed under the hidden policy, `0` if it failed |
| `failure_trace_json` | JSON string array | One to four noisy opaque diagnostic tokens |

Example values:

```json
{"environment_id": "env_02", "enabled_components_json": "[\"cmp_01\",\"cmp_08\",\"cmp_19\"]", "outcome": 0, "failure_trace_json": "[\"diag_014\",\"diag_096\"]"}
```

`labels.csv`

| Column | Type | Description |
|---|---|---|
| `case_id` | string | Joins to `probes.csv` and `case_index.csv` |
| `family_id` | string | Same grouping key as the observation table |
| `answer_json` | JSON object string | Hidden graph with `requires`, `conflicts`, and `gates` lists |
| `counterfactuals_json` | JSON object array string | 64 private configurations with their hidden outcomes, used only by the grader |

`answer_json` example:

```json
{"requires": [["cmp_03", "cmp_11"]], "conflicts": [["cmp_02", "cmp_15"]], "gates": [{"environment_id": "env_01", "relation": "requires", "left": "cmp_04", "right": "cmp_09"}]}
```

`requires` is directed: enabling `left` requires `right`. `conflicts` is unordered: both listed components may not be enabled together. A `gate` applies only in its listed environment and has either `requires` or `conflicts` semantics.

`case_index.csv`

| Column | Type | Description |
|---|---|---|
| `case_id` | string | Case identifier |
| `family_id` | string | Family-held-out split key |

## How The Data Is Generated

Each case draws its own hidden graph: 14 to 20 directed `requires` rules that form a DAG over a random component order, 6 to 10 unordered `conflicts` on pairs not already related, and 8 to 12 environment `gates` of either type. Historical probes are built in two ways. For every hidden rule, two witness probes start from a sampled passing configuration and are edited so that exactly that rule is violated. The remaining probes alternate between sampled passing configurations, repaired until they satisfy the policy, and random failing configurations. The 192 probes are then shuffled. Each probe carries one to three random diagnostic tokens from a 127-token vocabulary; with probability 0.75 a failing probe additionally carries the signature token of one violated rule. Signatures are case-specific keyed hashes, so the same rule shape has different tokens in different cases and the token vocabulary cannot be inverted to rule identities. Private counterfactual probes alternate between passing and failing configurations sampled the same way and are used only for scoring.

All randomness, every `case_id`, `family_id` and `probe_id`, and every signature token are derived by HMAC-SHA256 from a 256-bit secret held by the creator. The public generator code requires that secret and refuses to run without it, and the secret does not appear in any released file, in the source repository, or in its history. Cases are written in hashed-id order, so file order carries no generator index.

## Prepared Outputs

`prepare.py` writes a flat public directory plus a private answer directory. Every prepared file has a unique key and one row per case.

| File | Rows | Key | Contents |
|---|---:|---|---|
| public `train.csv` | 720 | `case_id` | `case_id`, `family_id`, and `probes_json`, a JSON array of that case's 192 historical probes, each with `probe_id`, `environment_id`, `enabled_components`, `outcome` and `failure_trace` |
| public `test.csv` | 180 | `case_id` | the same columns for the held-out cases |
| public `train_labels.csv` | 720 | `case_id` | `prediction_json`, the hidden graph of each training case in the submission format |
| public `sample_submission.csv` | 180 | `case_id` | one structurally valid placeholder graph per test case, built only from public probes |
| private `answers.csv` | 180 | `case_id` | `prediction_json`, holding the hidden graph (`requires`, `conflicts`, `gates`) plus a `counterfactuals` list of the 64 private probes; the same columns as `sample_submission.csv`, so the answer key is itself a perfect submission |

The public directory also holds `LICENSE`; no other raw document is copied into it, so nothing a solver receives names the dataset or its author. Every case uses the same inventories, `cmp_00` to `cmp_21` and `env_00` to `env_05`; they are fixed in the grader and stated here rather than repeated per row. Counterfactual probes are never public.

## Characteristics

- Each case has its own unrelated hidden graph, so identifiers cannot be memorized across cases.
- Directed `requires` rules form a DAG with 14 to 20 rules per case; `conflicts` has 6 to 10 rules; `gates` has 8 to 12 rules.
- Historical failures may activate several rules at once, tokens include decoys, and no single probe reveals a complete rule.
- The family keys support leak-free group-held-out splits: no family occurs in both prepared splits.

## Known Limitations

- **Fully synthetic; no real-world validity.** The policy shapes, probe distributions and diagnostic vocabulary are design choices of the generator, not measurements of any real release-control system. Methods that work here need not transfer to real deployment data.
- **Families are grouping keys, not distinct generators.** Every case is drawn from the same generative distribution; the family key only guarantees that identical case structure is never shared across the split. The held-out split therefore tests generalization across unseen cases, not across a shift in generation.
- **Uniform case shape.** Every case has exactly 22 components, six environments, 192 historical probes and the same inventories. Solutions are never tested on larger or ragged systems.
- **Witness probes are informative by construction.** Each hidden rule is violated in isolation by two probes, so a solver that can pair probes with rules has strong evidence for most rules; the difficulty lies in the decoy tokens, in the multi-rule failures, and in the environment-only rules.
- **Diagnostic tokens are a keyed hash with 127 buckets.** Within a case several rules can share a token, and the same token means different things in different cases. Tokens are evidence, not identifiers.
- **Counterfactual behaviour is scored on 64 private probes per case.** With that sample size, per-case behavioural accuracy has a resolution of about 1.6 percentage points.
- **Reproducibility is restricted by design.** The generator is public, but the released data can be regenerated only with the withheld secret. Anyone auditing the generator can run it with their own secret to obtain a statistically equivalent dataset, not this one.

## Provenance And License

All records are generated by an original deterministic synthetic generator written for this dataset. The package is released under Creative Commons Attribution 4.0 International (CC BY 4.0). Attribution: Esmael Abdlkadr, *Masked Release-Constraint Reconstruction Dataset* (2026).
