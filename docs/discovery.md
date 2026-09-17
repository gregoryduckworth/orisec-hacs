# Discovery

Adding a panel means knowing its address, and finding that address usually means
reading the DHCP leases off a router. This page is what came out of asking whether
Home Assistant could find a panel for you, what the integration does about it today,
and what is still unconfirmed against real hardware.

The short version: **nothing a panel sends can be listened for, but a panel can be asked
whether it is there.** So discovery here is an active scan, run when you open the config
flow, and the address you would have typed is offered as a suggestion instead.

## What happens when you add a panel

Opening **Add integration → Orisec Local** scans the networks Home Assistant's own
adapters are on before the form is drawn. Any panel that answers turns the **Host** field
into a list you can pick from; the field stays free text either way, so a panel the scan
cannot see is still added by typing its address.

What the scan does, precisely:

- It reads the enabled adapters from Home Assistant's
  [network configuration](https://www.home-assistant.io/integrations/network/) and takes
  the IPv4 network of each one. Loopback and link-local networks are skipped, and so is
  any network larger than 1024 addresses — a sweep of a `/16` would outlast anyone's
  patience in front of a form.
- Each address in those networks, broadcast address first, is sent one **info request**
  (`0x0014`) on UDP port `20202`. That is the same request the login datagram carries,
  so a panel is being asked something it already knows how to answer.
- Replies are collected for two seconds in total, not per address, so the whole scan
  takes about as long as a single timed-out read.
- The scan runs once per flow. Getting the password wrong and trying again redraws the
  same list rather than scanning a second time.

Two limits are worth knowing. The scan only probes port `20202`, because you have not
told it about a different port yet — a panel moved to another port has to be typed in.
And panels that are already configured are left out of the list, because picking one
only leads to *This panel is already configured*.

## How a panel is told apart from anything else on the port

Only that it answers, and answers in this protocol. A reply counts if it is a frame
`unpack_message` accepts: the declared length matches the datagram, the
[CRC](protocol.md#the-crc) over the rest of it matches, and the submessages inside do not
run off the end. Something else sitting on UDP `20202` — and something will, eventually —
does not produce a matching CRC-16/CCITT-FALSE by accident.

Nothing else is read out of the reply. The serial number that identifies a panel is not
in it, and would not be trustworthy before a login anyway, so the scan reports addresses
and the config flow still logs in before it saves anything.

## Scan without Home Assistant

`scripts/discover.py` runs the same scan from a terminal, which is the quickest way to
find out what your panel actually does:

```bash
python3 scripts/discover.py
python3 scripts/discover.py --network 192.168.1.0/24 --timeout 5
```

With no `--network` it guesses the `/24` around the address this machine sends from.
`--port` and `--timeout` override the defaults (`20202` and 2 seconds). Every address it
lists answered a probe; confirm one is really your panel with
[`probe.py`](troubleshooting.md#probe-a-panel-without-home-assistant).

## What was ruled out

Home Assistant's passive discovery mechanisms all need something a panel sends, or a
detail about a panel nobody has reported yet:

| Mechanism | Why it is not used | What would change that |
| --- | --- | --- |
| **DHCP** | Home Assistant matches a lease against a MAC address prefix or a hostname pattern in the manifest. No panel's MAC prefix or DHCP hostname has been reported. | One capture of a panel's lease. This is the cheapest discovery there is — no traffic at all — so it is the most useful thing to report. |
| **mDNS / zeroconf** | Requires the panel to advertise a service. Nothing has been seen advertised by one. | A `_something._udp.local.` record observed coming from a panel. |
| **SSDP / UPnP** | Requires the panel to answer an `M-SEARCH`, or send a `NOTIFY`. Neither has been seen. | The same: a capture showing one. |
| **A panel announcement** | The protocol as it is understood is strictly request and response; nothing in the captured traffic shows a panel speaking unprompted. | A capture of a panel sending something nobody asked for. |
| **The Orisec cloud** | This integration is local-only by design, and asking a vendor's service which panels you own is neither local nor necessary. | Nothing; this one is a choice rather than a limit. |

## What is still unconfirmed

Honest about the state of it: the scan is built on the protocol as
[documented here](protocol.md), not on a panel that was watched answering a scan.

- **Whether a panel answers an info request before a login.** It answers one *with* a
  login, in the same datagram. If it turns out to ignore an unauthenticated request, the
  scan finds nothing and the probe needs to become something else — that is the one knob
  to change, in `custom_components/orisec/discovery.py`.
- **Whether a panel answers a broadcast at all.** The broadcast address is probed first
  because a panel that answers it is found immediately, but the unicast sweep behind it
  is what the scan really relies on.
- **Whether anything else on your network answers on `20202`.** The CRC check is there to
  make that harmless, and an ignored reply is logged at debug level.

Either result is worth [reporting](https://github.com/gregoryduckworth/orisec-hacs/issues):
a scan that found your panel confirms the approach, and a scan that found nothing while
`probe.py` worked fine is what says the probe has to change.
