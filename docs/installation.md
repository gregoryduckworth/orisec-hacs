# Installation

## Requirements

- Home Assistant 2025.1.0 or newer (the floor declared in `hacs.json`).
- An Orisec panel with its LAN interface enabled, reachable from the Home Assistant
  host. The integration polls it directly over UDP; no cloud account or port forwarding
  is involved.
- A panel user password. Only ASCII characters are supported.

The integration itself has no third-party Python requirements, so installing it pulls
nothing else into your Home Assistant environment.

## Install through HACS

The repository is not in the HACS default store yet, so add it as a custom repository:

1. Open **HACS** in Home Assistant.
2. From the ⋮ menu, choose **Custom repositories**.
3. Add `https://github.com/gregoryduckworth/orisec-hacs` with the category
   **Integration**.
4. Open the new **Orisec HACS** entry and choose **Download**.
5. Restart Home Assistant.

HACS installs from a release asset (`hacs.json` sets `zip_release`), so it only ever
downloads `orisec.zip` from a published release — it cannot install an arbitrary commit.
If no release has been published yet, the download fails; see
[what HACS still needs](development.md#what-hacs-still-needs).

Then add your panel as described in [Configuration](configuration.md).

### Beta versions

Betas are published as [PEP 440](https://peps.python.org/pep-0440/) pre-releases
(`0.2.0b1`) and marked as pre-releases on GitHub. HACS hides them unless you ask for
them: open the repository in HACS, enable **Show beta versions** from its menu, then
redownload. Stable users are unaffected by that setting.

## Install a checkout for development

Because HACS installs from a release asset, it cannot install an unreleased checkout.
Link this repository into a Home Assistant config directory instead:

```bash
python3 scripts/install_local.py --config ~/homeassistant
```

That symlinks `custom_components/orisec` into the config directory, so edits in the
checkout take effect on the next Home Assistant restart with no reinstall step. The
directory has to contain a `configuration.yaml`, which is the script's check that it is
pointed at a real Home Assistant config and not, say, a sibling directory.

| Flag | What it does |
| --- | --- |
| `--config PATH` | The Home Assistant config directory to install into. Required. |
| `--copy` | Copy the component instead of symlinking it, for a config directory that cannot follow a link out to the checkout — a container bind mount, typically. |
| `--uninstall` | Remove whichever of the two is in place. |

After restarting Home Assistant, add the panel from the UI as usual.
[`scripts/probe.py`](troubleshooting.md#probe-a-panel-without-home-assistant) remains the
quicker way to check a change against real hardware without a restart.

## Uninstalling

Delete the config entry from **Settings → Devices & services** first, so Home Assistant
tears down the entities and closes the socket, then remove the integration from HACS (or
run `install_local.py --uninstall` for a linked checkout) and restart.
