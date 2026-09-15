"""Tests that the HACS/Home Assistant metadata stays valid and self-consistent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from homeassistant.config_entries import HANDLERS

from custom_components.orisec import DOMAIN, const
from custom_components.orisec.config_flow import OrisecConfigFlow

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOT = REPO_ROOT / "custom_components" / "orisec"
FLOW_SOURCE = (COMPONENT_ROOT / "config_flow.py").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((COMPONENT_ROOT / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def strings() -> dict:
    return json.loads((COMPONENT_ROOT / "strings.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def hacs_config() -> dict:
    return json.loads((REPO_ROOT / "hacs.json").read_text(encoding="utf-8"))


class TestManifest:
    @pytest.mark.parametrize(
        "key",
        [
            "domain",
            "name",
            "codeowners",
            "config_flow",
            "documentation",
            "integration_type",
            "iot_class",
            "issue_tracker",
            "version",
        ],
    )
    def test_declares_the_key_hacs_requires(self, manifest: dict, key: str) -> None:
        assert manifest.get(key)

    @pytest.mark.parametrize("key", ["documentation", "issue_tracker"])
    def test_publishes_the_url_over_https(self, manifest: dict, key: str) -> None:
        assert manifest[key].startswith("https://")

    def test_points_bug_reports_at_the_documented_repository(self, manifest: dict) -> None:
        assert manifest["issue_tracker"] == f"{manifest['documentation']}/issues"

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

    def test_is_added_through_the_user_interface(self, manifest: dict) -> None:
        assert manifest["config_flow"] is True


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


class TestStrings:
    def test_ships_english_translations_matching_the_source_strings(self, strings: dict) -> None:
        translations = json.loads((COMPONENT_ROOT / "translations" / "en.json").read_text(encoding="utf-8"))

        assert translations == strings

    @pytest.mark.parametrize("step_id", ["user", "reauth_confirm"])
    def test_describes_every_config_step_the_flow_can_show(self, strings: dict, step_id: str) -> None:
        assert strings["config"]["step"][step_id]["data"]

    def test_describes_the_options_step(self, strings: dict) -> None:
        assert strings["options"]["step"]["init"]["data"]

    def test_explains_every_form_error_the_flow_can_raise(self, strings: dict) -> None:
        raised = _quoted_arguments(FLOW_SOURCE, 'return None, {"base": "')

        assert raised <= set(strings["config"]["error"])

    def test_explains_every_reason_the_flow_can_abort_for(self, strings: dict) -> None:
        raised = _quoted_arguments(FLOW_SOURCE, 'reason="') | {
            "already_configured",
            "reauth_successful",
        }

        assert raised <= set(strings["config"]["abort"])

    def test_names_every_entity_that_asks_for_a_translated_name(self, strings: dict) -> None:
        source = (COMPONENT_ROOT / "sensor.py").read_text(encoding="utf-8")
        keys = _quoted_arguments(source, '_attr_translation_key = "')

        assert keys == set(strings["entity"]["sensor"])


def _quoted_arguments(source: str, prefix: str) -> set[str]:
    """Return the string literals that follow every occurrence of `prefix`."""

    return {part.split('"', 1)[0] for part in source.split(prefix)[1:]}


class TestConfigFlow:
    def test_registers_itself_for_the_integration_domain(self) -> None:
        assert HANDLERS[DOMAIN] is OrisecConfigFlow

    def test_starts_at_version_one(self) -> None:
        assert OrisecConfigFlow.VERSION == 1


class TestConstants:
    def test_exposes_a_unique_identifier_per_command(self) -> None:
        commands = {name: value for name, value in vars(const).items() if name.startswith("CMD_")}

        assert len(set(commands.values())) == len(commands)

    def test_every_command_fits_in_a_protocol_word(self) -> None:
        commands = [value for name, value in vars(const).items() if name.startswith("CMD_")]

        assert all(0 <= value <= 0xFFFF for value in commands)
