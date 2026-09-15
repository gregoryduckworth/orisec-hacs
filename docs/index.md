# Orisec HACS

Local-only Home Assistant control of [Orisec](https://orisec.co.uk/) alarm panels.

This project talks to a panel directly over UDP on your own network, without going
through the Orisec cloud. It ships a Home Assistant integration that is added from the
UI through a config flow, and the small Python client the integration is built on, both
under `custom_components/orisec`.

!!! warning "This project is under heavy development and will break without notice."

    Nothing here is stable yet. The client API, the protocol helpers, the repository
    layout, and the released versions themselves can all change or break at any time,
    with no deprecation period and no migration notes. Treat every release as
    experimental, pin an exact version if you depend on it, and expect to have to fix
    things up when you move between versions.

## Start here

<div class="grid cards" markdown>

- **[Installation](installation.md)** — add the repository to HACS, or link a checkout
  into a Home Assistant config for development.
- **[Configuration](configuration.md)** — what the config flow asks for, how a panel is
  identified, and how often it is polled.
- **[Entities](entities.md)** — the device and sensors a panel creates, and why the
  values are raw.
- **[Troubleshooting](troubleshooting.md)** — what each setup error means, and how to
  question a panel without Home Assistant.

</div>

## Going deeper

- **[Protocol](protocol.md)** — the frame layout, the CRC, and every command that has
  been identified so far.
- **[Python client](client.md)** — using `OrisecLocalClient` on its own, outside Home
  Assistant.
- **[Development](development.md)** — running the tests, the lint rules, and how CI is
  put together.
- **[Releasing](releasing.md)** — cutting a stable release or a beta.

## What works today

The integration logs in to a panel, reads what it is made of once at setup, and then
polls it on an interval you choose. Each configured zone becomes a sensor, alongside
diagnostic sensors for the panel's identity and its raw status block.

What it deliberately does *not* do yet is interpret those values. The bit layout of the
zone and panel status words has not been confirmed against hardware, so nothing here
guesses them into `on`/`off` binary sensors or an alarm control panel entity. If you
have a panel to test against, [`scripts/probe.py`](troubleshooting.md#probe-a-panel-without-home-assistant)
will dump what it reports, and an
[issue](https://github.com/gregoryduckworth/orisec-hacs/issues) with what you find is
the fastest way to move that along.
