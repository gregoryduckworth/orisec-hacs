"""Tests that the HACS/Home Assistant metadata stays valid and self-consistent."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from custom_components.orisec import DOMAIN, async_setup, const

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOT = REPO_ROOT / "custom_components" / "orisec"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((COMPONENT_ROOT / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hacs_config() -> dict:
    return json.loads((REPO_ROOT / "hacs.json").read_text(encoding="utf-8"))


class TestManifest:
    @pytest.mark.parametrize("key", ["domain", "name", "codeowners", "documentation", "iot_class", "version"])
    def test_declares_the_key_hacs_requires(self, manifest: dict, key: str) -> None:
        assert manifest.get(key)

    def test_uses_the_same_domain_as_the_constants_module(self, manifest: dict) -> None:
        assert manifest["domain"] == DOMAIN

    def test_lives_in_a_directory_named_after_its_domain(self, manifest: dict) -> None:
        assert manifest["domain"] == COMPONENT_ROOT.name

    def test_declares_a_known_iot_class(self, manifest: dict) -> None:
        assert manifest["iot_class"] in {
            "assumed_state",
            "calculated",
            "cloud_polling",
            "cloud_push",
            "local_polling",
            "local_push",
        }

    def test_publishes_a_three_part_version(self, manifest: dict) -> None:
        assert len(manifest["version"].split(".")) == 3

    def test_needs_no_third_party_requirements(self, manifest: dict) -> None:
        assert manifest["requirements"] == []


class TestHacsConfig:
    def test_names_the_repository(self, hacs_config: dict) -> None:
        assert hacs_config["name"]

    def test_pins_a_minimum_home_assistant_version(self, hacs_config: dict) -> None:
        assert len(hacs_config["homeassistant"].split(".")) == 3

    def test_installs_from_a_release_asset(self, hacs_config: dict) -> None:
        assert hacs_config["zip_release"] is True

    def test_expects_the_asset_the_release_workflow_builds(self, hacs_config: dict, manifest: dict) -> None:
        assert hacs_config["filename"] == f"{manifest['domain']}.zip"

    def test_names_an_asset_the_release_workflow_actually_attaches(self, hacs_config: dict) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        assert hacs_config["filename"] in workflow


class TestAsyncSetup:
    def test_reports_a_successful_setup(self) -> None:
        assert asyncio.run(async_setup(hass=None, config={})) is True


class TestConstants:
    def test_exposes_a_unique_identifier_per_command(self) -> None:
        commands = {name: value for name, value in vars(const).items() if name.startswith("CMD_")}

        assert len(set(commands.values())) == len(commands)

    def test_every_command_fits_in_a_protocol_word(self) -> None:
        commands = [value for name, value in vars(const).items() if name.startswith("CMD_")]

        assert all(0 <= value <= 0xFFFF for value in commands)
