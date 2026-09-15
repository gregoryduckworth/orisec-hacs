"""Focused tests for the release version bump and changelog helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.release import (
    Commit,
    ReleaseError,
    build_sections,
    bump_version,
    classify_commit,
    is_release_commit,
    parse_git_log,
    prepend_changelog,
    read_manifest_version,
    render_release_notes,
    update_changelog,
    write_manifest_version,
)


def _git_log(*records: tuple[str, str, str]) -> str:
    """Build git log output in the record/unit separated format the script reads."""
    return "".join(f"{sha}\x1f{subject}\x1f{body}\x1e" for sha, subject, body in records)


class BumpVersionTests(unittest.TestCase):
    def test_major_bump_resets_minor_and_patch(self) -> None:
        self.assertEqual(bump_version("1.4.7", "major"), "2.0.0")

    def test_minor_bump_resets_patch(self) -> None:
        self.assertEqual(bump_version("1.4.7", "minor"), "1.5.0")

    def test_patch_bump_increments_patch(self) -> None:
        self.assertEqual(bump_version("1.4.7", "patch"), "1.4.8")

    def test_bump_crosses_double_digit_boundary(self) -> None:
        self.assertEqual(bump_version("0.9.9", "minor"), "0.10.0")

    def test_unknown_release_type_is_rejected(self) -> None:
        with self.assertRaises(ReleaseError):
            bump_version("1.0.0", "hotfix")

    def test_non_semver_version_is_rejected(self) -> None:
        with self.assertRaises(ReleaseError):
            bump_version("1.0", "patch")


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.manifest = Path(self._tempdir.name) / "manifest.json"

    def test_version_is_read_from_manifest(self) -> None:
        self.manifest.write_text(json.dumps({"domain": "orisec", "version": "2.3.4"}))

        self.assertEqual(read_manifest_version(self.manifest), "2.3.4")

    def test_missing_version_field_is_rejected(self) -> None:
        self.manifest.write_text(json.dumps({"domain": "orisec"}))

        with self.assertRaises(ReleaseError):
            read_manifest_version(self.manifest)

    def test_invalid_json_is_rejected(self) -> None:
        self.manifest.write_text("{not json")

        with self.assertRaises(ReleaseError):
            read_manifest_version(self.manifest)

    def test_missing_manifest_is_rejected(self) -> None:
        with self.assertRaises(ReleaseError):
            read_manifest_version(self.manifest.parent / "absent.json")

    def test_write_updates_version_and_keeps_other_fields(self) -> None:
        self.manifest.write_text(json.dumps({"domain": "orisec", "version": "0.1.0"}, indent=2))

        write_manifest_version("0.2.0", self.manifest)

        self.assertEqual(
            json.loads(self.manifest.read_text()),
            {"domain": "orisec", "version": "0.2.0"},
        )

    def test_write_leaves_surrounding_formatting_untouched(self) -> None:
        original = '{\n  "domain": "orisec",\n  "codeowners": ["@someone"],\n  "version": "0.1.0"\n}\n'
        self.manifest.write_text(original)

        write_manifest_version("1.0.0", self.manifest)

        self.assertEqual(
            self.manifest.read_text(),
            original.replace('"version": "0.1.0"', '"version": "1.0.0"'),
        )

    def test_write_rejects_a_manifest_without_a_version_field(self) -> None:
        self.manifest.write_text(json.dumps({"domain": "orisec"}))

        with self.assertRaises(ReleaseError):
            write_manifest_version("1.0.0", self.manifest)

    def test_write_rejects_a_non_semver_version(self) -> None:
        self.manifest.write_text(json.dumps({"domain": "orisec", "version": "0.1.0"}))

        with self.assertRaises(ReleaseError):
            write_manifest_version("1.0", self.manifest)


class ParseGitLogTests(unittest.TestCase):
    def test_commits_are_split_into_sha_subject_and_body(self) -> None:
        raw = _git_log(("abc1234def", "feat: add zone polling", "Extra detail\n"))

        commits = parse_git_log(raw)

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].sha, "abc1234def")
        self.assertEqual(commits[0].short_sha, "abc1234")
        self.assertEqual(commits[0].subject, "feat: add zone polling")
        self.assertEqual(commits[0].body, "Extra detail")

    def test_empty_log_produces_no_commits(self) -> None:
        self.assertEqual(parse_git_log(""), [])

    def test_multiline_bodies_do_not_split_commits(self) -> None:
        raw = _git_log(
            ("1111111", "fix: handle timeout", "line one\nline two"),
            ("2222222", "docs: expand readme", ""),
        )

        commits = parse_git_log(raw)

        self.assertEqual(
            [commit.subject for commit in commits],
            [
                "fix: handle timeout",
                "docs: expand readme",
            ],
        )


class ClassifyCommitTests(unittest.TestCase):
    def test_feature_commit_lands_in_features_with_short_sha(self) -> None:
        section, entry = classify_commit(Commit("abcdef1234", "feat: add area names"))

        self.assertEqual(section, "Features")
        self.assertEqual(entry, "add area names (abcdef1)")

    def test_scope_is_kept_in_the_entry(self) -> None:
        _, entry = classify_commit(Commit("abcdef1234", "fix(api): retry login"))

        self.assertEqual(entry, "**api**: retry login (abcdef1)")

    def test_bang_marks_a_breaking_change(self) -> None:
        section, _ = classify_commit(Commit("abcdef1234", "feat!: drop cloud support"))

        self.assertEqual(section, "Breaking Changes")

    def test_breaking_change_footer_marks_a_breaking_change(self) -> None:
        section, _ = classify_commit(
            Commit("abcdef1234", "refactor: rework client", "BREAKING CHANGE: renamed client")
        )

        self.assertEqual(section, "Breaking Changes")

    def test_unknown_type_falls_back_to_other_changes(self) -> None:
        section, entry = classify_commit(Commit("abcdef1234", "wibble: something odd"))

        self.assertEqual(section, "Other Changes")
        self.assertEqual(entry, "wibble: something odd (abcdef1)")

    def test_non_conventional_subject_falls_back_to_other_changes(self) -> None:
        section, entry = classify_commit(Commit("abcdef1234", "Tighten payload parsing"))

        self.assertEqual(section, "Other Changes")
        self.assertEqual(entry, "Tighten payload parsing (abcdef1)")


class BuildSectionsTests(unittest.TestCase):
    def test_sections_follow_the_documented_order(self) -> None:
        commits = [
            Commit("1111111", "chore: tidy up"),
            Commit("2222222", "fix: correct crc"),
            Commit("3333333", "feat: add areas"),
            Commit("4444444", "feat!: drop cloud"),
        ]

        sections = build_sections(commits)

        self.assertEqual(
            list(sections),
            ["Breaking Changes", "Features", "Bug Fixes", "Maintenance"],
        )

    def test_commits_of_the_same_type_are_grouped_in_order(self) -> None:
        commits = [Commit("1111111", "fix: first"), Commit("2222222", "fix: second")]

        self.assertEqual(
            build_sections(commits)["Bug Fixes"],
            ["first (1111111)", "second (2222222)"],
        )

    def test_no_commits_produces_no_sections(self) -> None:
        self.assertEqual(build_sections([]), {})

    def test_previous_release_commits_are_excluded(self) -> None:
        commits = [Commit("1111111", "chore(release): v0.2.0"), Commit("2222222", "fix: a bug")]

        self.assertEqual(build_sections(commits), {"Bug Fixes": ["a bug (2222222)"]})

    def test_release_commit_is_recognised_with_and_without_the_v_prefix(self) -> None:
        self.assertTrue(is_release_commit(Commit("1111111", "chore(release): v1.2.3")))
        self.assertTrue(is_release_commit(Commit("1111111", "chore(release): 1.2.3")))

    def test_ordinary_chore_commits_are_not_treated_as_releases(self) -> None:
        self.assertFalse(is_release_commit(Commit("1111111", "chore: bump dependency to v1.2.3")))


class RenderReleaseNotesTests(unittest.TestCase):
    def test_notes_include_heading_sections_and_compare_link(self) -> None:
        sections = build_sections([Commit("1111111", "feat: add areas")])

        notes = render_release_notes(
            "0.2.0",
            sections,
            repository="gregoryduckworth/orisec-hacs",
            previous_tag="v0.1.0",
            release_date="2026-09-15",
        )

        self.assertEqual(
            notes,
            "## v0.2.0 - 2026-09-15\n"
            "\n"
            "### Features\n"
            "- add areas (1111111)\n"
            "\n"
            "**Full Changelog**: "
            "https://github.com/gregoryduckworth/orisec-hacs/compare/v0.1.0...v0.2.0\n",
        )

    def test_first_release_links_to_the_commit_list(self) -> None:
        notes = render_release_notes(
            "0.1.0",
            {},
            repository="gregoryduckworth/orisec-hacs",
            previous_tag=None,
            release_date="2026-09-15",
        )

        self.assertIn(
            "**Full Changelog**: https://github.com/gregoryduckworth/orisec-hacs/commits/v0.1.0",
            notes,
        )

    def test_release_without_commits_states_so(self) -> None:
        notes = render_release_notes("0.1.1", {}, release_date="2026-09-15")

        self.assertIn("No user facing changes were recorded", notes)

    def test_repository_is_optional(self) -> None:
        notes = render_release_notes("0.1.1", {}, release_date="2026-09-15")

        self.assertNotIn("Full Changelog", notes)


class ChangelogTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.changelog = Path(self._tempdir.name) / "CHANGELOG.md"

    def test_first_entry_gets_the_file_header(self) -> None:
        result = prepend_changelog("", "## v0.1.0 - 2026-09-15\n")

        self.assertTrue(result.startswith("# Changelog\n"))
        self.assertIn("## v0.1.0 - 2026-09-15", result)

    def test_newer_entry_is_placed_above_older_entries(self) -> None:
        first = prepend_changelog("", "## v0.1.0 - 2026-09-14\n")

        result = prepend_changelog(first, "## v0.2.0 - 2026-09-15\n")

        self.assertLess(result.index("## v0.2.0"), result.index("## v0.1.0"))

    def test_header_is_not_duplicated_across_releases(self) -> None:
        first = prepend_changelog("", "## v0.1.0 - 2026-09-14\n")

        result = prepend_changelog(first, "## v0.2.0 - 2026-09-15\n")

        self.assertEqual(result.count("# Changelog"), 1)

    def test_update_changelog_creates_a_missing_file(self) -> None:
        update_changelog("## v0.1.0 - 2026-09-15\n", self.changelog)

        self.assertTrue(self.changelog.exists())
        self.assertIn("## v0.1.0 - 2026-09-15", self.changelog.read_text())

    def test_update_changelog_keeps_previous_entries(self) -> None:
        update_changelog("## v0.1.0 - 2026-09-14\n", self.changelog)

        update_changelog("## v0.2.0 - 2026-09-15\n", self.changelog)

        contents = self.changelog.read_text()
        self.assertIn("## v0.1.0 - 2026-09-14", contents)
        self.assertIn("## v0.2.0 - 2026-09-15", contents)


if __name__ == "__main__":
    unittest.main()
