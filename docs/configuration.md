# Configuration

Everything is configured from the Home Assistant UI. There is nothing to put in
`configuration.yaml`.

## Adding a panel

1. Go to **Settings → Devices & services → Add integration** and pick **Orisec Local**.
2. Fill in the form:

    | Field | Meaning |
    | --- | --- |
    | **Host** | The IP address or hostname of the panel on your network. |
    | **Password** | A panel user password. Only ASCII characters are supported. |
    | **Port** | The UDP port the panel listens on. Defaults to `20202`; leave it unless you changed it. |

3. Submit. The flow logs in to the panel and reads its layout *before* it saves
   anything, so a wrong address or password is reported on the form rather than after
   the fact. If it fails, the host and port you typed are offered back — only the
   password is cleared.

Give the panel a static address, or a DHCP reservation. Nothing here discovers a panel
that has moved on its own; you would have to correct the entry by hand.

### How a panel is identified

The entry's unique ID is the panel's serial number, read during that first login, and
the entry is titled `Orisec <serial number>`. Two consequences follow:

- The same panel cannot be added twice. A second attempt aborts with *This panel is
  already configured*.
- Re-adding a panel that has moved to a new IP address updates the existing entry's host
  instead of creating a second entry.

## Options

The **Configure** button on the entry opens a single option:

| Option | Range | Default |
| --- | --- | --- |
| **Poll interval** | 5–3600 seconds | 30 seconds |

This is how often zone status and the panel status block are read. Saving it reloads the
entry, so the new interval takes effect immediately.

Every poll is one login plus two reads over UDP on your own network, so a short interval
is cheap in absolute terms — but it is still a panel, not a web server. Start at the
default and shorten it only if you have a reason to.

## Re-authentication

If the panel starts rejecting the stored password — someone changed the user code, say —
the failing poll raises a re-authentication prompt rather than leaving the entities
quietly stale. Home Assistant shows the entry as needing attention and asks for a new
password for the panel at that host.

The new password is proved against the panel before it is saved, and the serial number
is checked as well: if that address now answers as a *different* panel, the flow aborts
with *That address belongs to a different panel than the one being re-authenticated*
rather than silently repointing the entry.

## Reloading

Reload the entry (**⋮ → Reload** on the entry) after reprogramming the panel. Zone and
area names are read once at setup, not on every poll, so newly programmed zones only
appear after a reload. Changing the poll interval reloads the entry for you.
