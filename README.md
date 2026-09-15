# Orisec HACS

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
