# Orisec HACS

[![CI](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/ci.yml)
[![Validate](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/validate.yml)
[![Docs](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/docs.yml/badge.svg)](https://github.com/gregoryduckworth/orisec-hacs/actions/workflows/docs.yml)

HACS repository for local-only Home Assistant control of Orisec alarm panels.

**📚 Full documentation: <https://gregoryduckworth.github.io/orisec-hacs/>**

> [!WARNING]
> **This project is under heavy development and will break without notice.**
>
> Nothing here is stable yet. The client API, the protocol helpers, the repository
> layout, and the released versions themselves can all change or break at any time,
> with no deprecation period and no migration notes. Treat every release as
> experimental, pin an exact version if you depend on it, and expect to have to fix
> things up when you move between versions.

This repository talks to Orisec alarm panels directly over UDP on your own network,
without relying on the Orisec cloud. It ships a Home Assistant integration that is added
from the UI through a config flow, and the small Python client the integration is built
on, both under `custom_components/orisec`.

## Installing

The repository is not in the HACS default store yet, so add it as a custom repository:
**HACS → ⋮ → Custom repositories**, `https://github.com/gregoryduckworth/orisec-hacs`,
category **Integration**. Download it, then restart Home Assistant.

HACS installs from a release asset, so it cannot install an unreleased checkout — see
[Installation](https://gregoryduckworth.github.io/orisec-hacs/installation/) for beta
versions and for linking a checkout into a Home Assistant config instead.

## Setting up a panel

Everything is configured from the Home Assistant UI; there is nothing to put in
`configuration.yaml`.

1. **Settings → Devices & services → Add integration → Orisec Local.**
2. Pick the panel from the **Host** list, or enter its IP address or hostname if it is
   not there. Opening the form scans your network for panels first; the UDP port
   defaults to `20202`.
3. Enter a user password the panel accepts. The flow logs in before it saves anything,
   so a wrong address or password is reported on the form rather than after the fact.

The panel's serial number identifies the entry, so the same panel cannot be added twice,
and moving it to a new IP address updates the existing entry instead of creating a second
one. **Options** (the *Configure* button) sets how often the panel is polled, between 5
and 3600 seconds, defaulting to 30.

Full details, including re-authentication:
[Configuration](https://gregoryduckworth.github.io/orisec-hacs/configuration/). What that
scan sends, and what it cannot do yet:
[Discovery](https://gregoryduckworth.github.io/orisec-hacs/discovery/).

## What you get

One device per panel, with one sensor per configured zone plus diagnostic sensors for
the serial number, model, configured zones, areas, and the raw panel status block.

> [!NOTE]
> Zone status and panel status are surfaced as the raw values the panel returns. The bit
> layout of those words has not been confirmed against hardware, so nothing here guesses
> them into `on`/`off` binary sensors or an alarm control panel entity. Use
> `scripts/probe.py` against your own panel to work out what the bits mean, and open an
> issue with what you find.

See [Entities](https://gregoryduckworth.github.io/orisec-hacs/entities/) for the full
list, and
[Troubleshooting](https://gregoryduckworth.github.io/orisec-hacs/troubleshooting/) when
something does not work.

## Documentation

| Page | Covers |
| --- | --- |
| [Installation](https://gregoryduckworth.github.io/orisec-hacs/installation/) | HACS install, betas, and running a checkout |
| [Configuration](https://gregoryduckworth.github.io/orisec-hacs/configuration/) | The config flow, options and re-authentication |
| [Discovery](https://gregoryduckworth.github.io/orisec-hacs/discovery/) | Finding panels on the network, and what passive discovery would need |
| [Entities](https://gregoryduckworth.github.io/orisec-hacs/entities/) | The device and sensors a panel creates |
| [Troubleshooting](https://gregoryduckworth.github.io/orisec-hacs/troubleshooting/) | Setup errors, debug logging and `probe.py` |
| [Protocol](https://gregoryduckworth.github.io/orisec-hacs/protocol/) | Frame layout, the CRC and every known command |
| [Python client](https://gregoryduckworth.github.io/orisec-hacs/client/) | Using `OrisecLocalClient` on its own |
| [Development](https://gregoryduckworth.github.io/orisec-hacs/development/) | Tests, lint, CI and HACS validation |
| [Releasing](https://gregoryduckworth.github.io/orisec-hacs/releasing/) | Cutting a stable release or a beta |

The pages are the markdown files under [`docs/`](docs/), published to GitHub Pages by
`.github/workflows/docs.yml`.

## Development in one screen

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest                 # tests, with a 100% coverage gate on the component
.venv/bin/ruff check .           # lint
.venv/bin/ruff format --check .  # formatting

.venv/bin/pip install -r requirements-docs.txt
.venv/bin/mkdocs serve           # preview this documentation locally
```

The suite runs entirely offline: the UDP socket is the only mocked boundary, so every
packet the client builds and parses is asserted on real bytes. See
[Development](https://gregoryduckworth.github.io/orisec-hacs/development/) for the
detail.

## License

Released under the [MIT License](LICENSE).
