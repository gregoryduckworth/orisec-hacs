"""Tests that the published documentation stays in step with the code.

`mkdocs build --strict` already rejects a broken link or a page missing from the
nav, but it only runs in the docs workflow. These tests repeat the cheap parts of
that in the main suite, and add the checks mkdocs cannot make: that the pages
still describe the commands, defaults and entities the code actually has.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from custom_components.orisec import const

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
SITE_URL = "https://gregoryduckworth.github.io/orisec-hacs/"

FENCED_BLOCK = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*$", re.MULTILINE)


def _prose(path: Path) -> str:
    """Return a page's text with fenced code blocks removed."""

    return FENCED_BLOCK.sub("", path.read_text(encoding="utf-8"))


def _slugify(heading: str) -> str:
    """Slug a heading the way Python-Markdown's table of contents does."""

    collapsed = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"[-\s]+", "-", collapsed)


def _anchors(path: Path) -> set[str]:
    return {_slugify(heading) for heading in HEADING.findall(_prose(path))}


def _flatten_nav(entries: list) -> list[str]:
    """Return every file path in the nav, whatever it is nested under."""

    files: list[str] = []
    for entry in entries:
        for value in entry.values() if isinstance(entry, dict) else [entry]:
            files.extend(_flatten_nav(value) if isinstance(value, list) else [value])
    return files


@pytest.fixture(scope="module")
def mkdocs_config() -> dict:
    return yaml.safe_load((REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nav_files(mkdocs_config: dict) -> list[str]:
    return _flatten_nav(mkdocs_config["nav"])


@pytest.fixture(scope="module")
def pages() -> list[Path]:
    return sorted(DOCS_ROOT.rglob("*.md"))


def _page(name: str) -> str:
    return (DOCS_ROOT / name).read_text(encoding="utf-8")


class TestSite:
    def test_publishes_from_the_documented_url(self, mkdocs_config: dict) -> None:
        assert mkdocs_config["site_url"] == SITE_URL

    def test_offers_every_page_in_the_navigation(self, nav_files: list[str], pages: list[Path]) -> None:
        listed = {DOCS_ROOT / name for name in nav_files}

        assert set(pages) == listed

    def test_navigates_only_to_pages_that_exist(self, nav_files: list[str]) -> None:
        missing = [name for name in nav_files if not (DOCS_ROOT / name).is_file()]

        assert missing == []

    def test_links_between_pages_resolve(self, pages: list[Path]) -> None:
        broken = [
            (page.name, target)
            for page in pages
            for target in MARKDOWN_LINK.findall(_prose(page))
            if not target.startswith(("http://", "https://", "#", "mailto:"))
            and not (page.parent / target.split("#", 1)[0]).is_file()
        ]

        assert broken == []

    def test_links_to_sections_that_exist(self, pages: list[Path]) -> None:
        broken = []
        for page in pages:
            for target in MARKDOWN_LINK.findall(_prose(page)):
                if target.startswith(("http://", "https://", "mailto:")) or "#" not in target:
                    continue
                path, anchor = target.split("#", 1)
                linked = page.parent / path if path else page
                if linked.is_file() and anchor not in _anchors(linked):
                    broken.append((page.name, target))

        assert broken == []


class TestBuild:
    @pytest.fixture(scope="class")
    def workflow(self) -> str:
        return (REPO_ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")

    def test_installs_the_pinned_documentation_tooling(self, workflow: str) -> None:
        assert "requirements-docs.txt" in workflow

    def test_fails_the_build_on_a_broken_link(self, workflow: str) -> None:
        assert "mkdocs build --strict" in workflow

    def test_pins_every_documentation_dependency(self) -> None:
        requirements = (REPO_ROOT / "requirements-docs.txt").read_text(encoding="utf-8").split()

        assert requirements and all("==" in requirement for requirement in requirements)


class TestProtocolPage:
    @pytest.fixture(scope="class")
    def protocol(self) -> str:
        return _page("protocol.md")

    @pytest.mark.parametrize(
        ("name", "value"),
        sorted((name, value) for name, value in vars(const).items() if name.startswith("CMD_")),
    )
    def test_documents_every_command_the_client_knows(self, protocol: str, name: str, value: int) -> None:
        assert f"`0x{value:04X}`" in protocol

    def test_documents_the_port_a_panel_listens_on(self, protocol: str) -> None:
        assert f"**{const.DEFAULT_PORT}**" in protocol

    def test_documents_how_long_a_read_waits(self, protocol: str) -> None:
        assert f"**{const.DEFAULT_TIMEOUT:g} seconds**" in protocol


class TestConfigurationPage:
    @pytest.fixture(scope="class")
    def configuration(self) -> str:
        return _page("configuration.md")

    def test_documents_the_default_port(self, configuration: str) -> None:
        assert f"`{const.DEFAULT_PORT}`" in configuration

    def test_documents_the_poll_interval_the_options_flow_allows(self, configuration: str) -> None:
        assert f"{const.MIN_SCAN_INTERVAL}–{const.MAX_SCAN_INTERVAL} seconds" in configuration
        assert f"{const.DEFAULT_SCAN_INTERVAL} seconds" in configuration


class TestEntitiesPage:
    def test_names_every_entity_the_integration_creates(self) -> None:
        strings = json.loads(
            (REPO_ROOT / "custom_components" / "orisec" / "strings.json").read_text(encoding="utf-8")
        )
        entities = _page("entities.md")

        undocumented = [
            entity["name"]
            for entity in strings["entity"]["sensor"].values()
            if f"**{entity['name']}**" not in entities
        ]

        assert undocumented == []


class TestDevelopmentPage:
    @pytest.fixture(scope="class")
    def development(self) -> str:
        return _page("development.md")

    def test_describes_every_test_module(self, development: str) -> None:
        modules = sorted(path.name for path in (REPO_ROOT / "tests").glob("test_*.py"))

        undocumented = [name for name in modules if f"tests/{name}" not in development]

        assert undocumented == []

    def test_describes_every_workflow(self, development: str) -> None:
        workflows = sorted(path.name for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"))

        undocumented = [name for name in workflows if f"workflows/{name}" not in development]

        assert undocumented == []

    def test_describes_every_module_the_integration_ships(self, development: str) -> None:
        component = REPO_ROOT / "custom_components" / "orisec"
        modules = sorted(path.name for path in component.glob("*.py"))

        undocumented = [name for name in modules if f"orisec/{name}" not in development]

        assert undocumented == []


class TestReadme:
    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_points_readers_at_the_published_site(self, readme: str) -> None:
        assert SITE_URL in readme

    def test_links_to_every_published_page(self, readme: str, pages: list[Path]) -> None:
        # index.md is the site root, which the link above already covers.
        unlinked = [
            page.name for page in pages if page.name != "index.md" and f"{SITE_URL}{page.stem}/" not in readme
        ]

        assert unlinked == []
