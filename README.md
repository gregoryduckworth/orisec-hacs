# Orisec HACS

[![CI](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml)
[![Validate](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml)

Minimal HACS repository for local-only communication with Orisec alarm panels.

> [!WARNING]
> **This project is under heavy development and will break without notice.**
>
> Nothing here is stable yet. The client API, the protocol helpers, the repository
> layout, and the released versions themselves can all change or break at any time,
> with no deprecation period and no migration notes. Treat every release as
> experimental, pin an exact version if you depend on it, and expect to have to fix
> things up when you move between versions.

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
- `scripts/probe.py` — command line probe that dumps what a real panel reports
- `scripts/install_local.py` — link or copy the component into a Home Assistant config

## Example

```python
from custom_components.orisec.api import OrisecLocalClient

with OrisecLocalClient("192.168.1.50", "1234") as client:
    client.login()
    print(client.read_panel_model())
    print(client.read_zone_names(client.read_max_zones()))
```

## Installing and testing locally

### Probe a panel without Home Assistant

The fastest check against real hardware. It needs only the panel IP and a user
password, and runs every known read in turn:

```bash
python3 scripts/probe.py --host 192.168.1.50 --password 1234
```

Each read is attempted independently, so a command your panel does not support is
reported as one failed row rather than aborting the run. `--port` and `--timeout`
override the defaults.

### Install into a Home Assistant config

HACS installs from a release asset (`zip_release`), so it cannot install an unreleased
checkout. Link this checkout into a Home Assistant config directory instead:

```bash
python3 scripts/install_local.py --config ~/homeassistant
```

That symlinks `custom_components/orisec` into the config, so edits here take effect on
the next Home Assistant restart with no reinstall step. Use `--copy` when the config
directory cannot follow a link out to this checkout — a container bind mount, typically —
and `--uninstall` to remove whichever of the two is in place.

> **What to expect:** the component currently ships the protocol client only. It has no
> config flow and no platforms, so Home Assistant will load it but no integration appears
> in the UI and no entities are created. Until that layer exists, `scripts/probe.py` is the
> way to exercise the panel.

## Development

Install the test tooling into a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
```

### Tests

```bash
.venv/bin/pytest
```

The suite runs entirely offline. The UDP socket is the only mocked boundary, so every
packet the client builds and parses is asserted on real bytes rather than on mocked
decoder calls. Coverage of `custom_components/orisec` is measured with branch coverage
enabled and the run fails below 100%, so a new code path cannot land untested.

Useful variations:

```bash
.venv/bin/pytest -k protocol          # one area
.venv/bin/pytest --no-cov             # skip the coverage gate while iterating
```

The tests are grouped by concern:

| File | Covers |
| --- | --- |
| `tests/test_protocol.py` | CRC, frame and submessage encoding, every decode rejection path |
| `tests/test_api_transport.py` | socket lifecycle, addressing, timeouts, `query`/`query_many` |
| `tests/test_api_session.py` | login, session and model caching, auth failures, keepalive |
| `tests/test_api_reads.py` | every panel read command and payload decoder |
| `tests/test_integration_metadata.py` | `manifest.json`, `hacs.json` and `const` consistency |
| `tests/test_release.py` | the version bump and changelog helpers in `scripts/release.py` |

The 100% gate covers `custom_components/orisec` — the code HACS ships. `scripts/release.py`
is tested but not gated; it currently sits at 77%, with the git and `main()` plumbing
uncovered.

### Lint

Lint and formatting are checked with [ruff](https://docs.astral.sh/ruff/), configured in
`pyproject.toml`:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Continuous integration

- `.github/workflows/ci.yml` — runs ruff and the test suite, including the coverage gate,
  on Python 3.12 and 3.13 for every push to `main` and every pull request.
- `.github/workflows/validate.yml` — runs Home Assistant `hassfest` and HACS repository
  validation, also on a weekly schedule so upstream requirement changes surface before a
  release does.
- `.github/workflows/prepare-release.yml` — cuts a release: bumps the version, writes the
  changelog, tags, and publishes.
- `.github/workflows/release.yml` — runs on a GitHub release published by hand and attaches
  the `orisec.zip` asset that HACS installs from.

Require the `Lint`, `Test (Python 3.12)`, `Test (Python 3.13)`, `Hassfest` and `HACS`
checks in branch protection for `main` so untested code cannot reach the branch releases
are cut from.

### HACS validation

HACS validates that a HACS *user* could install the integration, so it reads `hacs.json`
and `manifest.json` over unauthenticated `raw.githubusercontent.com` rather than from the
checkout. That means repository settings, not just files, decide whether the job passes:

- The repository must be **public**, or both reads 404 and HACS reports the misleading
  `invalid 'hacs.json'` / `expected a dictionary. Got None` instead of a 404.
- `LICENSE` must carry a licence HACS recognises (MIT here). HACS reads
  `license.spdx_id` from GitHub's repository metadata, which GitHub derives from the
  **default branch** only — so a licence added on a PR branch still reports red until it
  merges.

Validation ignores the `brands`, `description` and `topics` checks. To drop those ignores,
get the `orisec` domain accepted into
[home-assistant/brands](https://github.com/home-assistant/brands) and set a repository
description and topics in GitHub settings.

### What HACS still needs

A green `Validate` run means the metadata is valid; it does not mean a user can install
the integration yet. Outstanding, in the order they block a user:

| Gap | Why it matters | Where it is fixed |
| --- | --- | --- |
| No release published | `hacs.json` sets `zip_release`, so HACS only ever downloads `orisec.zip` from a release asset. With no release there is nothing to download and installation fails outright. | Run **Prepare Release**, then publish the draft |
| No config flow or platforms | Home Assistant loads the component but registers no integration and no entities, so an install does nothing visible. | Add `config_flow.py` and at least one platform |
| Repository description and topics unset | The two ignored checks above. | GitHub repository settings |
| `orisec` not in `home-assistant/brands` | The third ignored check, and required for listing in the HACS default store. Custom-repository installs work without it. | PR to [home-assistant/brands](https://github.com/home-assistant/brands) |

Two smaller notes: `hassfest` warns that `async_setup` is defined without a
`CONFIG_SCHEMA`, which is resolved by the config flow work above; and
`OrisecLocalClient` uses blocking sockets, so the integration layer must call it through
`async_add_executor_job` rather than directly on the event loop.

## Releasing

Releases are cut by the **Prepare Release** workflow
(`.github/workflows/prepare-release.yml`), run manually from the Actions tab on the default
branch. Pick the bump you want:

| Bump    | `0.1.4` becomes |
| ------- | --------------- |
| `patch` | `0.1.5`         |
| `minor` | `0.2.0`         |
| `major` | `1.0.0`         |

The workflow runs the full test suite, including the coverage gate, and stops there if
anything fails. Then it:

1. Bumps `version` in `custom_components/orisec/manifest.json`, the field HACS reads. Unlike
   a manual release, this bump is committed to the default branch, so `main` and the tag
   never drift.
2. Generates release notes from the commits since the previous tag and prepends them to
   `CHANGELOG.md`.
3. Commits, tags `vX.Y.Z`, and pushes.
4. Builds `orisec.zip` and publishes the GitHub release with the notes and that asset
   attached. It is attached here rather than by `release.yml`, because a release created
   with the default `GITHUB_TOKEN` does not trigger other workflows. `release.yml` still
   covers releases published by hand, and gates the asset on a green `ci.yml` run so a
   hand-published release with failing tests never becomes installable.

Tick **dry run** to see the resulting version and changelog in the workflow summary without
committing, tagging, or publishing anything.

### Beta releases

Tick **beta** to publish a [PEP 440](https://peps.python.org/pep-0440/) pre-release instead.
The bump you pick chooses the base version, and the beta number counts up from there:

| From      | Bump    | Beta | Result    |
| --------- | ------- | ---- | --------- |
| `0.1.0`   | `minor` | yes  | `0.2.0b1` |
| `0.2.0b1` | any     | yes  | `0.2.0b2` |
| `0.2.0b2` | any     | no   | `0.2.0`   |

Once a beta line is open the base version is already decided, so `release_type` no longer
applies to it: a further beta increments the beta number, and an unticked run promotes the
same base to stable. Both ignore the bump you pick, so to change the base, finish or abandon
the line first.

Betas are marked as pre-releases on GitHub and are deliberately kept out of `CHANGELOG.md`,
which would otherwise carry an entry per beta and a near-empty one for the stable release.
The stable release that promotes them compares against the last *stable* tag instead, so its
notes cover everything the betas shipped.

To install a beta through HACS, open the repository in HACS, enable **Show beta versions** in
its menu, then redownload. HACS only offers pre-releases while that is on, so stable users are
unaffected.

### Changelog entries

Notes are built from the non-merge commits since the previous tag. [Conventional
commit](https://www.conventionalcommits.org/) subjects are grouped into sections (`feat:` →
Features, `fix:` → Bug Fixes, and so on); a `!` marker or a `BREAKING CHANGE:` footer moves a
commit to Breaking Changes. Commits that do not follow the convention are listed verbatim
under Other Changes, so nothing is dropped.

The version in `manifest.json` is the starting point for the bump, so the first run of the
workflow moves the current `0.1.0` on to `0.1.1`, `0.2.0`, or `1.0.0`. To publish the current
version as-is instead, tag it by hand once.

## License

Released under the [MIT License](LICENSE).
