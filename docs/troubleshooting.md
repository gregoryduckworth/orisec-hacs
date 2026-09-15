# Troubleshooting

## Errors the setup form can show

| Message | What it means | What to check |
| --- | --- | --- |
| *Could not reach the panel.* | The panel did not answer within the timeout, or the datagram did not get there at all. | The host and port; that the panel's LAN interface is enabled; that Home Assistant and the panel can reach each other (no VLAN or firewall in between). Confirm with [`probe.py`](#probe-a-panel-without-home-assistant) from the same host. |
| *The panel rejected that password.* | The panel answered, but did not acknowledge the login. | That the password is a valid user password and contains only ASCII characters. |
| *Unexpected error* | The flow hit something it does not have a case for. | The Home Assistant log — the flow logs the traceback under `custom_components.orisec`. Please [report it](https://github.com/gregoryduckworth/orisec-hacs/issues). |
| *This panel is already configured.* | A config entry with that serial number exists. | Nothing: if the panel changed address, this attempt has already updated the existing entry's host. |
| *That address belongs to a different panel...* | Re-authentication found a different serial number at that address. | Whether the address now points at another panel. Delete and re-add the entry if the swap was intentional. |

## The entities went unavailable

Every entity comes from a single poll, so they fail together. The log entry from
`custom_components.orisec` carries the reason:

- **Timed out waiting for response** — the panel stopped answering. Check that it is
  powered and still on the same address.
- **Panel did not acknowledge login** — the password stopped working, which raises a
  [re-authentication prompt](configuration.md#re-authentication) rather than a plain
  failure.
- **CRC mismatch** or **Payload length does not match header** — something answered on
  that port with a frame that is not the protocol this client speaks. Check the port, and
  that nothing else on the network answers on it.

## A new zone is missing

Zone and area names are read once at setup, not on every poll, so a zone programmed into
the panel after the entry was created only appears once you
[reload the entry](configuration.md#reloading).

## Turning on debug logging

Add this to `configuration.yaml` and restart, or set it for one session from
**Developer tools → Services → `logger.set_level`**:

```yaml
logger:
  default: warning
  logs:
    custom_components.orisec: debug
```

The coordinator logs each failed update, and the config flow logs the traceback behind
an *Unexpected error*.

## Probe a panel without Home Assistant

The fastest check against real hardware. It needs only the panel's address and a user
password, runs every known read in turn, and prints what comes back:

```bash
python3 scripts/probe.py --host 192.168.1.50 --password 1234
```

Each read is attempted independently, so a command your panel does not support is
reported as one failed row rather than aborting the run. `--port` and `--timeout`
override the defaults (`20202` and 2 seconds).

```text
probing 192.168.1.50:20202 (timeout 2.0s)

login: ok

serial number: 000123456789
panel model: 4
panel status (raw): 00 00 00 00 00 00 00 00 00 00 00 00 00 00
max zones: 32
configured zones: 3
areas: 1
zone names:
      1. Front Door
      2. Hall
      3. Landing
zone status:
      1. 0
      2. 0
      3. 0
motion events:
      1. 0
      2. 0
      3. 0
area names:
      1. House
```

The script imports the client straight out of the checkout, so it needs no Home
Assistant install and no dependencies beyond the standard library.

## Reporting a problem

[Open an issue](https://github.com/gregoryduckworth/orisec-hacs/issues) with the panel
model, the relevant log lines, and — if the problem is about what a value means — the
`probe.py` output alongside what the panel was actually doing at the time. That last
pairing is what it takes to confirm a bit layout, which is the main thing blocking
[richer entities](entities.md#why-the-values-are-raw).
