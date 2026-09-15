# Python client

`custom_components.orisec.api.OrisecLocalClient` is the whole panel-facing surface. The
Home Assistant integration is a thin layer over it, and
[`scripts/probe.py`](troubleshooting.md#probe-a-panel-without-home-assistant) uses it
directly, so it works fine on its own:

```python
from custom_components.orisec.api import OrisecLocalClient

with OrisecLocalClient("192.168.1.50", "1234") as client:
    client.login()
    print(client.read_panel_model())
    print(client.read_zone_names(client.read_zone_count()))
```

It is deliberately synchronous and has no dependencies outside the standard library.

## Constructing one

```python
OrisecLocalClient(host, password, *, port=20202, timeout=2.0, socket_factory=None)
```

| Argument | Meaning |
| --- | --- |
| `host` | Panel IP address or hostname. |
| `password` | Panel user password. ASCII only; anything else raises `AuthenticationError` at login. |
| `port` | UDP port the panel listens on. |
| `timeout` | Seconds to wait for a reply to any single request. |
| `socket_factory` | Returns the socket to use. The hook the tests swap a fake panel in through. |

The socket is opened lazily on the first send and reopened after a `close()`, so a
client can outlive the socket it was using. As a context manager it opens on entry and
closes on exit.

## Reads

| Method | Returns |
| --- | --- |
| `login()` | Nothing. Authenticates, and caches the session block and model number. |
| `keepalive()` | Nothing. Fire-and-forget; no reply is waited for. |
| `read_session_info()` | The raw session block cached at login. `ResponseError` before login. |
| `read_panel_model()` | `int` model number, cached after the first read. |
| `read_panel_status_raw()` | `bytes` — the panel status block, uninterpreted. |
| `read_serial_number()` | `str`, truncated at the first NUL. |
| `read_max_zones()` | `int` — zones the panel can support. |
| `read_zone_count()` | `int` — zones actually configured. |
| `read_area_count()` | `int` — areas configured. |
| `read_zone_names(count)` | `list[str]`, exactly `count` long. |
| `read_area_names(count)` | `list[str]`, exactly `count` long. |
| `read_zone_status(count)` | `list[int]`, one status word per zone. |
| `read_motion_events(count)` | `list[int]`, one uint16 per zone. |

`query()` and `query_many()` sit underneath all of those if you need to send a command
the client has no named method for — `query_many()` is what puts several submessages in
one datagram — and `send()` transmits without waiting for a reply.

## Composite reads

Two methods bundle the reads the integration actually needs, split by how often the
answers change:

```python
layout = client.read_layout()          # serial number, model, zone names, area names
state = client.read_state(layout.zone_count)   # panel status, zone status
```

`read_layout()` returns a frozen `PanelLayout` — the things that only change when the
panel is reprogrammed, which the integration reads once at setup. Its `zone_count`
property is simply how many zone names came back.

`read_state()` returns a frozen `PanelState` — `panel_status` bytes and a `zone_status`
list — which is what gets polled. Passing `zone_count=0` skips the zone read entirely.

## Sessions and keepalive

The protocol is connectionless UDP, so there is no reliable way to tell a session that
quietly expired from a panel that stopped answering. The integration therefore logs in
again on every poll instead of holding a session open and calling `keepalive()`. For a
long-lived script of your own, `keepalive()` is there — but re-logging in is the pattern
that has actually been exercised.

## Errors

```text
OrisecError (RuntimeError)
├── AuthenticationError   the panel rejected the password, or it is not ASCII
└── ResponseError         the reply was missing, malformed, or the wrong length

ProtocolError (ValueError)  raised inside protocol.py; the client re-raises it
                            as ResponseError
```

A timeout or an unreachable host surfaces as `OrisecError`; anything the socket itself
rejects comes through as the underlying `OSError`. Catching `(OrisecError, OSError)` is
what the integration does to mean "could not talk to the panel", with
`AuthenticationError` peeled off first to mean "could, but was refused".

## Using it from Home Assistant

The client blocks, so every call from the integration goes through
`hass.async_add_executor_job` rather than being awaited on the event loop. If you build
on it inside Home Assistant, do the same — a blocking socket read on the event loop
stalls everything else.
