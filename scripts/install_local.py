#!/usr/bin/env python3
"""Install this checkout into a local Home Assistant config for testing.

HACS installs the integration from a release asset, so it cannot install an
unreleased checkout. This copies -- or, by default, symlinks -- the component
straight into a Home Assistant config directory instead.

    python3 scripts/install_local.py --config ~/homeassistant

A symlink means edits in this checkout take effect on the next Home Assistant
restart, with no reinstall step. Use ``--copy`` for a container or any config
directory that cannot follow a link out to this checkout, and ``--uninstall``
to remove whichever of the two is there.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "custom_components" / "orisec"


class InstallError(RuntimeError):
    """Raised when the component cannot be installed or removed."""


def resolve_target(config_dir: Path) -> Path:
    """Return the ``custom_components/orisec`` path inside ``config_dir``."""

    config_dir = config_dir.expanduser()
    if not config_dir.is_dir():
        raise InstallError(f"Home Assistant config directory not found: {config_dir}")
    if not (config_dir / "configuration.yaml").is_file():
        raise InstallError(
            f"{config_dir} has no configuration.yaml, so it does not look like a "
            "Home Assistant config directory"
        )
    return config_dir / "custom_components" / SOURCE.name


def remove_existing(target: Path) -> bool:
    """Remove a previous install, returning whether anything was removed."""

    if target.is_symlink() or target.is_file():
        target.unlink()
        return True
    if target.is_dir():
        shutil.rmtree(target)
        return True
    return False


def install(config_dir: Path, *, copy: bool = False) -> Path:
    """Link or copy the component into ``config_dir`` and return the target path."""

    target = resolve_target(config_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    remove_existing(target)

    if copy:
        shutil.copytree(SOURCE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        target.symlink_to(SOURCE, target_is_directory=True)

    return target


def uninstall(config_dir: Path) -> Path | None:
    """Remove the component from ``config_dir``, returning the path if it existed."""

    target = resolve_target(config_dir)
    return target if remove_existing(target) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", required=True, type=Path, help="Home Assistant config directory")
    parser.add_argument("--copy", action="store_true", help="copy the files instead of symlinking")
    parser.add_argument("--uninstall", action="store_true", help="remove a previous install")
    args = parser.parse_args(argv)

    try:
        if args.uninstall:
            removed = uninstall(args.config)
            print(f"removed {removed}" if removed else "nothing to remove")
        else:
            target = install(args.config, copy=args.copy)
            verb = "copied" if args.copy else "linked"
            print(f"{verb} {SOURCE} -> {target}")
            print("restart Home Assistant to pick up the change")
    except InstallError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except OSError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
