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
- `scripts/release.py` — version bump and changelog generation used by the release workflow

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
- `.github/workflows/prepare-release.yml` — cuts a release: bumps the version, writes the
  changelog, tags, and publishes.
- `.github/workflows/release.yml` — runs on a GitHub release published by hand and attaches
  the `orisec.zip` asset that HACS installs from.

HACS validation currently ignores the `brands`, `description` and `topics` checks. To drop
those ignores, get the `orisec` domain accepted into
[home-assistant/brands](https://github.com/home-assistant/brands) and set a repository
description and topics in GitHub settings.

## Releasing

Releases are cut by the **Prepare Release** workflow
(`.github/workflows/prepare-release.yml`), run manually from the Actions tab on the default
branch. Pick the bump you want:

| Bump    | `0.1.4` becomes |
| ------- | --------------- |
| `patch` | `0.1.5`         |
| `minor` | `0.2.0`         |
| `major` | `1.0.0`         |

The workflow runs the test suite, then:

1. Bumps `version` in `custom_components/orisec/manifest.json`, the field HACS reads. Unlike
   a manual release, this bump is committed to the default branch, so `main` and the tag
   never drift.
2. Generates release notes from the commits since the previous tag and prepends them to
   `CHANGELOG.md`.
3. Commits, tags `vX.Y.Z`, and pushes.
4. Builds `orisec.zip` and publishes the GitHub release with the notes and that asset
   attached. It is attached here rather than by `release.yml`, because a release created
   with the default `GITHUB_TOKEN` does not trigger other workflows. `release.yml` still
   covers releases published by hand.

Tick **dry run** to see the resulting version and changelog in the workflow summary without
committing, tagging, or publishing anything.

### Changelog entries

Notes are built from the non-merge commits since the previous tag. [Conventional
commit](https://www.conventionalcommits.org/) subjects are grouped into sections (`feat:` →
Features, `fix:` → Bug Fixes, and so on); a `!` marker or a `BREAKING CHANGE:` footer moves a
commit to Breaking Changes. Commits that do not follow the convention are listed verbatim
under Other Changes, so nothing is dropped.

The version in `manifest.json` is the starting point for the bump, so the first run of the
workflow moves the current `0.1.0` on to `0.1.1`, `0.2.0`, or `1.0.0`. To publish the current
version as-is instead, tag it by hand once.
