# Development

## Repository layout

| Path | What lives there |
| --- | --- |
| `custom_components/orisec/config_flow.py` | The UI flow that adds, re-authenticates and retunes a panel |
| `custom_components/orisec/__init__.py` | Config entry setup, teardown and reload |
| `custom_components/orisec/coordinator.py` | The polling loop, run off the event loop |
| `custom_components/orisec/sensor.py` | The entities built from what the panel reports |
| `custom_components/orisec/entity.py` | The device every entity attaches to |
| `custom_components/orisec/api.py` | High-level local UDP client |
| `custom_components/orisec/discovery.py` | The network scan that finds panels for the flow |
| `custom_components/orisec/protocol.py` | Packet and submessage encoding and decoding |
| `custom_components/orisec/const.py` | Known command identifiers and defaults |
| `custom_components/orisec/strings.json` | Flow and entity text, mirrored into `translations/en.json` |
| `scripts/release.py` | Version bump and changelog generation used by the release workflow |
| `scripts/probe.py` | Command line probe that dumps what a real panel reports |
| `scripts/discover.py` | Command line scan for panels, without Home Assistant |
| `scripts/install_local.py` | Link or copy the component into a Home Assistant config |
| `docs/` | This site |

## Setting up

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
```

That pulls in Home Assistant itself, via
[`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component),
so the config flow and the platforms are tested against a real `hass`. The pinned
version of that package decides which Home Assistant release the suite runs against;
keep `hacs.json`'s `homeassistant` floor at or below it.

To run the integration against a real Home Assistant while you work, see
[installing a checkout](installation.md#install-a-checkout-for-development).

## Tests

```bash
.venv/bin/pytest
```

The suite runs entirely offline. The UDP socket is the only mocked boundary, so every
packet the client builds and parses is asserted on real bytes rather than on mocked
decoder calls — the integration tests drive a `FakePanel` that answers real protocol
frames, so a config flow or an entity is exercised through the same encoding and
decoding a real panel would meet. Coverage of `custom_components/orisec` is measured with
branch coverage enabled and the run fails below 100%, so a new code path cannot land
untested.

Useful variations:

```bash
.venv/bin/pytest -k protocol          # one area
.venv/bin/pytest --no-cov             # skip the coverage gate while iterating
```

The tests are grouped by concern:

| File | Covers |
| --- | --- |
| `tests/test_protocol.py` | CRC, frame and submessage encoding, every decode rejection path |
| `tests/test_api_transport.py` | Socket lifecycle, addressing, timeouts, `query`/`query_many` |
| `tests/test_api_session.py` | Login, session and model caching, auth failures, keepalive |
| `tests/test_api_reads.py` | Every panel read command and payload decoder |
| `tests/test_config_flow.py` | Adding a panel, the errors the form can show, reauth, options |
| `tests/test_discovery.py` | Which addresses a scan probes, and what it accepts as a panel |
| `tests/test_init.py` | Config entry setup, polling, reload and teardown |
| `tests/test_sensor.py` | The entities and the device a config entry creates |
| `tests/test_integration_metadata.py` | `manifest.json`, `hacs.json`, `strings.json` and `const` consistency |
| `tests/test_docs.py` | That this site stays in step with the code and is wired into the build |
| `tests/test_install_local.py` | Linking, copying and removing a local install |
| `tests/test_release.py` | The version bump and changelog helpers in `scripts/release.py` |

The 100% gate covers `custom_components/orisec` — the code HACS ships. The helpers under
`scripts/` are tested but not gated.

## Lint

Lint and formatting are checked with [ruff](https://docs.astral.sh/ruff/), configured in
`pyproject.toml`:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Documentation

This site is [MkDocs](https://www.mkdocs.org/) with the
[Material](https://squidfunk.github.io/mkdocs-material/) theme. The pages are the
markdown files under `docs/`, and `mkdocs.yml` holds the nav.

```bash
.venv/bin/pip install -r requirements-docs.txt
.venv/bin/mkdocs serve          # live-reloading preview on http://127.0.0.1:8000
.venv/bin/mkdocs build --strict # what CI runs
```

`--strict` turns warnings into failures, and `mkdocs.yml` raises link and nav problems to
warnings, so a page that is renamed without updating the links to it, or added without
being put in the nav, fails the build rather than shipping broken.

Adding a page means creating the file *and* adding it to the `nav` in `mkdocs.yml`.

`.github/workflows/docs.yml` builds the site on every pull request and deploys it to
GitHub Pages on every push to `main`. Deployment needs **Settings → Pages → Build and
deployment → Source** set to **GitHub Actions** once, by hand; until then the build still
runs and the deploy step is what fails.

## Continuous integration

| Workflow | What it does |
| --- | --- |
| `.github/workflows/ci.yml` | Runs ruff and the test suite, including the coverage gate, on Python 3.12 and 3.13 for every push to `main` and every pull request |
| `.github/workflows/validate.yml` | Runs Home Assistant `hassfest` and HACS repository validation, also on a weekly schedule so upstream requirement changes surface before a release does |
| `.github/workflows/docs.yml` | Builds this site on every pull request and publishes it from `main` |
| `.github/workflows/prepare-release.yml` | Cuts a release: bumps the version, writes the changelog, tags, and publishes |
| `.github/workflows/release.yml` | Runs on a GitHub release published by hand and attaches the `orisec.zip` asset that HACS installs from |

Require the `Lint`, `Test (Python 3.12)`, `Test (Python 3.13)`, `Hassfest`, `HACS` and
`Build docs` checks in branch protection for `main` so untested code cannot reach the
branch releases are cut from.

## HACS validation

HACS validates that a HACS *user* could install the integration, so it reads `hacs.json`
and `manifest.json` over unauthenticated `raw.githubusercontent.com` rather than from the
checkout. That means repository settings, not just files, decide whether the job passes:

- The repository must be **public**, or both reads 404 and HACS reports the misleading
  `invalid 'hacs.json'` / `expected a dictionary. Got None` instead of a 404.
- `LICENSE` must carry a licence HACS recognises (MIT here). HACS reads `license.spdx_id`
  from GitHub's repository metadata, which GitHub derives from the **default branch**
  only — so a licence added on a PR branch still reports red until it merges.

Validation ignores the `brands`, `description` and `topics` checks. To drop those
ignores, get the `orisec` domain accepted into
[home-assistant/brands](https://github.com/home-assistant/brands) and set a repository
description and topics in GitHub settings.

## What HACS still needs

A green `Validate` run means the metadata is valid; it does not mean a user can install
the integration yet. Outstanding, in the order they block a user:

| Gap | Why it matters | Where it is fixed |
| --- | --- | --- |
| No release published | `hacs.json` sets `zip_release`, so HACS only ever downloads `orisec.zip` from a release asset. With no release there is nothing to download and installation fails outright. | Run **Prepare Release**, then publish the draft |
| Repository description and topics unset | The two ignored checks above. | GitHub repository settings |
| `orisec` not in `home-assistant/brands` | The third ignored check, and required for listing in the HACS default store. Custom-repository installs work without it. | PR to [home-assistant/brands](https://github.com/home-assistant/brands) |
