# Masked Release-Constraint Reconstruction Dataset

An original synthetic CPU benchmark for reconstructing hidden release-policy constraints from anonymized historical deployment probes: 900 independent cases, each with 22 opaque components, six environments, 96 historical probes with pass/fail outcomes and noisy diagnostic tokens, and a hidden graph of directed `requires` rules, unordered `conflicts`, and environment-only `gates`.

## The withheld secret

Every random draw, every `case_id`, `family_id` and `probe_id`, and every diagnostic token is derived by HMAC-SHA256 from a 256-bit secret that is not published. `generate.py` refuses to run without a secret (`MRCR_SECRET` or `MRCR_SECRET_FILE`). Running it with your own secret produces a statistically equivalent dataset, not the released one, so the released answers cannot be recomputed from this repository.

## Contents

| File | Purpose |
|---|---|
| `generate.py` | the secret-keyed case generator |
| `DATASET_DESCRIPTION.md` | full dataset documentation: schema, construction, characteristics and limitations |
| `LICENSE` | CC BY 4.0 notice |

## License

Dataset and generator are released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution: Esmael Abdlkadr, *Masked Release-Constraint Reconstruction Dataset* (2026). No production source code, customer records, repositories, or third-party data are used.
