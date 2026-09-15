# Orisec HACS

[![CI](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml)
[![Validate](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml)

Minimal HACS repository for local-only communication with Orisec alarm panels.

This repository exposes the known Orisec LAN APIs as a small Python client under
`custom_components/orisec` so a Home Assistant integration can talk to the panel
directly over UDP without relying on the Orisec cloud.

## Exposed local APIs

The client currently exposes the known local commands for:

- login
- session info
- panel model info
- panel status (raw bytes)
- serial number
- max/configured zone counts
- zone names
- area count
- area names
- zone status
- motion events
- keepalive

## Repository layout

- `custom_components/orisec/api.py` — high-level local UDP client
- `custom_components/orisec/protocol.py` — packet/submessage encoding and decoding
- `custom_components/orisec/const.py` — known command identifiers

## Example

```python
from custom_components.orisec.api import OrisecLocalClient

with OrisecLocalClient("192.168.1.50", "1234") as client:
    client.login()
    print(client.read_panel_model())
    print(client.read_zone_names(client.read_max_zones()))
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Lint and formatting are checked with [ruff](https://docs.astral.sh/ruff/), configured in
`pyproject.toml`:

```bash
ruff check .
ruff format --check .
```

## Continuous integration

- `.github/workflows/ci.yml` — runs ruff and the unit tests on Python 3.12 and 3.13 for
  every push to `main` and every pull request.
- `.github/workflows/validate.yml` — runs Home Assistant `hassfest` and HACS repository
  validation, also on a weekly schedule so upstream requirement changes surface before a
  release does.
- `.github/workflows/release.yml` — runs on a published GitHub release.

HACS validation currently ignores the `brands`, `description` and `topics` checks. To drop
those ignores, get the `orisec` domain accepted into
[home-assistant/brands](https://github.com/home-assistant/brands) and set a repository
description and topics in GitHub settings.

## Releasing

`hacs.json` sets `zip_release`, so HACS installs the integration from a release asset
rather than from the repository tree.

1. Publish a GitHub release tagged `vX.Y.Z` (for example `v0.2.0`).
2. The release workflow runs the tests, rewrites `custom_components/orisec/manifest.json`
   so its `version` matches the tag (without the leading `v`), zips
   `custom_components/orisec` into `orisec.zip`, and attaches it to the release.

The version rewrite happens only in the workflow checkout, so remember to bump the
`version` in `manifest.json` on `main` as well.
