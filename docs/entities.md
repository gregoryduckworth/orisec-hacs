# Entities

Adding a panel creates one device, named after the config entry and carrying the panel's
serial number and model number in the device registry. Everything below attaches to it.

## Zone sensors

One sensor per configured zone, named as the panel names that zone (or `Zone 3` when the
panel returns an empty name).

| | |
| --- | --- |
| **State** | The status word the panel returns for that zone, as an integer |
| **Attributes** | `zone` — the panel's own 1-based number for the zone, so an automation can address it the way the panel does |
| **Unique ID** | `<serial number>_zone_<n>`, falling back to the config entry ID for a panel that reports no serial number |

## Diagnostic sensors

These are in Home Assistant's *Diagnostic* category, so they sit apart from the zones on
the device page.

| Entity | State | Notes |
| --- | --- | --- |
| **Panel status** | The raw panel status block, as a spaced hex string | Re-read on every poll |
| **Serial number** | The panel's serial number | Read once at setup |
| **Model** | The panel's model number | Read once at setup |
| **Configured zones** | How many zones the panel has configured | Read once at setup |
| **Areas** | How many areas the panel has configured | `areas` attribute carries the area names. Read once at setup |

The four read once at setup only change when the panel is reprogrammed, so they are
fetched with the layout rather than polled. [Reload the
entry](configuration.md#reloading) to pick up changes to them.

## Why the values are raw

!!! note "Nothing here guesses at bit layouts."

    Zone status and panel status are surfaced exactly as the panel returns them. The bit
    layout of those words has not been confirmed against hardware, so the integration
    does not turn them into `on`/`off` binary sensors, a `binary_sensor.motion` per zone,
    or an `alarm_control_panel` entity — any of which would mean inventing a mapping and
    then being quietly wrong about your alarm system.

    Use [`scripts/probe.py`](troubleshooting.md#probe-a-panel-without-home-assistant)
    against your own panel to work out what the bits mean, and
    [open an issue](https://github.com/gregoryduckworth/orisec-hacs/issues) with what you
    find.

In the meantime a template sensor is the supported way to interpret a value yourself:

```yaml
template:
  - binary_sensor:
      - name: Hall PIR active
        state: "{{ states('sensor.orisec_hall') | int(0) > 0 }}"
```

That is a guess about your panel, not a recommendation — confirm it against what the
zone actually does before you rely on it.

## Availability

All of these come from one coordinator, so if a poll fails the whole set goes
unavailable together. A failure that looks like a rejected password raises a
[re-authentication prompt](configuration.md#re-authentication) instead.
