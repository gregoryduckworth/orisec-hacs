# Protocol

Everything here was worked out by watching traffic between a panel and the official
apps. It is not an official specification, it is not complete, and the parts that are
marked as unconfirmed really are unconfirmed. `custom_components/orisec/protocol.py`
holds the encoder and decoder; `custom_components/orisec/const.py` holds the command
identifiers.

## Transport

A panel listens for UDP datagrams on port **20202** by default. There is no connection
and no handshake: each request is one datagram, and each response is one datagram back
from the panel. The client sends from an ephemeral port and waits up to **2 seconds**
for a reply before giving up.

Because it is connectionless, a session that quietly expired is indistinguishable from a
panel that stopped answering. The integration deals with that by logging in again on
every poll rather than holding a session open — see
[Client](client.md#sessions-and-keepalive).

## Frame layout

Every value is little-endian.

```text
+----------------+----------------------------------+----------------+
| length         | one or more submessages          | CRC            |
| uint16         |                                  | uint16         |
+----------------+----------------------------------+----------------+
```

- **length** counts the whole frame, including its own two bytes and the two CRC bytes.
- **CRC** is computed over everything before it — the length field and the submessages.

The decoder rejects a frame whose declared length disagrees with the bytes received,
whose CRC does not match, or whose submessages run off the end of the payload. Each of
those raises `ProtocolError`, which the client surfaces as `ResponseError`.

### Submessages

One frame carries one or more submessages, each one a request for, or an answer about,
a single command:

```text
+----------+--------+--------+-----------+-----------------+
| cmd_id   | start  | count  | data_len  | data            |
| uint16   | uint16 | uint16 | uint16    | data_len bytes  |
+----------+--------+--------+-----------+-----------------+
```

| Field | Meaning |
| --- | --- |
| `cmd_id` | Which command this is. The panel echoes it on the response. |
| `start` | The first item to read, 1-based. Always `1` in this client. |
| `count` | How many items to read. `1` for scalars; the zone or area count for the list reads. |
| `data_len` | Length of `data`. |
| `data` | The request payload (a password, say) or the panel's answer. |

### A worked example

Asking for the serial number — command `0x0262`, one item, no payload:

```text
0c 00   62 02   01 00   01 00   00 00   ae 57
|       |       |       |       |       |
|       |       |       |       |       CRC
|       |       |       |       data_len = 0
|       |       |       count = 1
|       |       start = 1
|       cmd_id = 0x0262
length = 12
```

Several submessages can share one datagram, which is how login works: the login command
and the info request go out together, and the panel answers both in one frame.

```text
18 00  01 00 01 00 01 00 04 00 31 32 33 34  14 00 01 00 01 00 00 00  57 9c
       \__ 0x0001 login, data "1234" ____/  \__ 0x0014 info request/
```

## Commands

| Command | ID | Request payload | Response |
| --- | --- | --- | --- |
| Login | `0x0001` | The user password as ASCII | Presence of the response is the acknowledgement |
| Session info | `0x0002` | — | Opaque session block, returned alongside the login response |
| Panel status | `0x0003` | — | 14 raw bytes; layout unconfirmed |
| Keepalive | `0x0006` | `01 00 02 04`, `count` = 2 | None; sent without waiting |
| Info request | `0x0014` | — | Answered with `0x0063` |
| Info response | `0x0063` | — | Four bytes; the model number is the second uint16 |
| Serial number | `0x0262` | — | ASCII, NUL-terminated |
| Max zones | `0x045A` | — | uint16: zones the panel can support |
| Zone names | `0x0460` | `count` = number of zones | NUL-separated ASCII names |
| Area names | `0x083E` | `count` = number of areas | NUL-separated ASCII names |
| Area count | `0x0842` | — | uint16: configured areas |
| Zone count | `0x2462` | — | uint16: configured zones |
| Zone status | `0x2850` | `count` = number of zones | One status word per zone; see below |
| Motion events | `0x277E` | `count` = number of zones | One uint16 per zone; meaning unconfirmed |

### Payload quirks

**Zone status comes in two widths.** Some panels answer with one byte per zone, others
with one uint16 per zone. The client picks based on the payload length — `count` bytes
means 8-bit values, `count * 2` means 16-bit — and rejects anything else rather than
guessing at a partial read.

**Name lists are NUL-separated, not NUL-terminated per item.** A trailing empty entry is
dropped, a short list is padded with empty strings up to `count`, and a long one is
truncated, so a name read always yields exactly `count` entries and cannot shift every
zone's name by one.

**Strings are ASCII.** A name or serial number that is not decodable as ASCII is a
`ResponseError`, not a mojibake entity name.

**Status words are opaque.** Panel status and zone status are passed through unchanged.
Nothing in this repository claims to know what their bits mean; see
[why the values are raw](entities.md#why-the-values-are-raw).

## The CRC

A 16-bit CRC with polynomial `0x1021`, an initial value of `0xFFFF`, MSB first, and no
final XOR or reflection — the parameters usually called CRC-16/CCITT-FALSE. It checks
`0x29B1` against the standard `123456789` test vector. The helper is named
`crc16_xmodem` after the polynomial family; the initial value is what distinguishes it
from XMODEM proper.

## Anything missing?

If you have traffic from a panel that shows a command not listed here — arming,
disarming, event history, anything — [an issue with the
capture](https://github.com/gregoryduckworth/orisec-hacs/issues) is genuinely useful.
The command table above is the limit of what is known, not the limit of what panels do.
