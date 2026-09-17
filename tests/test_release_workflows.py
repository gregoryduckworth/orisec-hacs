"""Tests that Prepare Release actually hands the new tag to the Release workflow.

A release created with the default ``GITHUB_TOKEN`` does not fire the ``release``
event, so the two workflows are wired together by an explicit
``workflow_dispatch``. That wiring is otherwise only exercised by cutting a real
release, so it is pinned here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # YAML reads the `on:` key as the boolean True.
    return workflow[True]


def _step(workflow: dict, job: str, name: str) -> dict:
    steps = [step for step in workflow["jobs"][job]["steps"] if step.get("name") == name]
    assert len(steps) == 1, f"expected one {name!r} step in {job!r}, found {len(steps)}"
    return steps[0]


@pytest.fixture(scope="module")
def prepare() -> dict:
    return _workflow("prepare-release.yml")


@pytest.fixture(scope="module")
def release() -> dict:
    return _workflow("release.yml")


class TestPrepareRelease:
    def test_starts_the_release_workflow_for_the_tag_it_pushed(self, prepare: dict) -> None:
        step = _step(prepare, "prepare", "Start the Release workflow")

        assert 'gh workflow run release.yml --ref "$TAG"' in step["run"]

    def test_grants_the_permission_needed_to_start_a_workflow(self, prepare: dict) -> None:
        assert prepare["jobs"]["prepare"]["permissions"]["actions"] == "write"

    def test_leaves_the_release_drafted_for_the_release_workflow_to_publish(self, prepare: dict) -> None:
        step = _step(prepare, "prepare", "Draft the GitHub release")

        assert "--draft" in step["run"]

    def test_leaves_the_installable_asset_to_the_release_workflow(self, prepare: dict) -> None:
        scripts = "\n".join(step.get("run", "") for step in prepare["jobs"]["prepare"]["steps"])

        assert "orisec.zip" not in scripts


class TestRelease:
    def test_can_be_started_by_prepare_release(self, release: dict) -> None:
        assert "workflow_dispatch" in _triggers(release)

    def test_still_runs_for_a_release_published_by_hand(self, release: dict) -> None:
        assert _triggers(release)["release"]["types"] == ["published"]

    def test_refuses_a_dispatch_that_is_not_from_a_tag(self, release: dict) -> None:
        step = _step(release, "tag", "Resolve the tag being released")

        assert "refs/tags/" in step["run"]

    def test_builds_the_code_the_released_tag_points_at(self, release: dict) -> None:
        step = _step(release, "release", "Check out the repository")

        assert step["with"]["ref"] == "${{ needs.tag.outputs.tag }}"

    def test_gates_publishing_on_a_green_ci_run(self, release: dict) -> None:
        assert "ci" in release["jobs"]["release"]["needs"]

    def test_publishes_the_draft_only_once_the_asset_is_attached(self, release: dict) -> None:
        names = [step.get("name") for step in release["jobs"]["release"]["steps"]]

        assert "--draft=false" in _step(release, "release", "Publish the release")["run"]
        assert names.index("Attach the archive to the release") < names.index("Publish the release")
