"""Tests for the local Home Assistant install helper."""

from __future__ import annotations

import pytest

from scripts.install_local import (
    SOURCE,
    InstallError,
    install,
    main,
    resolve_target,
    uninstall,
)


@pytest.fixture
def config_dir(tmp_path):
    """A directory that looks like a Home Assistant config."""
    (tmp_path / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
    return tmp_path


class TestResolveTarget:
    def test_rejects_a_directory_that_does_not_exist(self, tmp_path) -> None:
        with pytest.raises(InstallError, match="config directory not found"):
            resolve_target(tmp_path / "absent")

    def test_rejects_a_directory_without_a_configuration_file(self, tmp_path) -> None:
        with pytest.raises(InstallError, match="no configuration.yaml"):
            resolve_target(tmp_path)

    def test_points_at_custom_components_inside_the_config(self, config_dir) -> None:
        assert resolve_target(config_dir) == config_dir / "custom_components" / "orisec"


class TestInstall:
    def test_links_back_to_this_checkout_by_default(self, config_dir) -> None:
        target = install(config_dir)

        assert target.is_symlink()
        assert target.resolve() == SOURCE.resolve()

    def test_linked_install_exposes_the_manifest(self, config_dir) -> None:
        target = install(config_dir)

        assert (target / "manifest.json").is_file()

    def test_copy_install_leaves_real_files_not_a_link(self, config_dir) -> None:
        target = install(config_dir, copy=True)

        assert not target.is_symlink()
        assert (target / "manifest.json").is_file()

    def test_copy_install_omits_bytecode(self, config_dir) -> None:
        target = install(config_dir, copy=True)

        assert not (target / "__pycache__").exists()

    def test_creates_the_custom_components_directory_when_missing(self, config_dir) -> None:
        assert not (config_dir / "custom_components").exists()

        install(config_dir)

        assert (config_dir / "custom_components").is_dir()

    def test_replaces_a_previous_copy_install(self, config_dir) -> None:
        install(config_dir, copy=True)

        target = install(config_dir)

        assert target.is_symlink()

    def test_replaces_a_previous_linked_install(self, config_dir) -> None:
        install(config_dir)

        target = install(config_dir, copy=True)

        assert not target.is_symlink()


class TestUninstall:
    def test_removes_a_linked_install(self, config_dir) -> None:
        install(config_dir)

        removed = uninstall(config_dir)

        assert removed is not None
        assert not removed.exists()

    def test_removes_a_copied_install(self, config_dir) -> None:
        install(config_dir, copy=True)

        removed = uninstall(config_dir)

        assert removed is not None
        assert not removed.exists()

    def test_reports_nothing_to_remove_when_not_installed(self, config_dir) -> None:
        assert uninstall(config_dir) is None


class TestMain:
    def test_reports_success_for_a_linked_install(self, config_dir, capsys) -> None:
        assert main(["--config", str(config_dir)]) == 0
        assert "linked" in capsys.readouterr().out

    def test_reports_success_for_a_copied_install(self, config_dir, capsys) -> None:
        assert main(["--config", str(config_dir), "--copy"]) == 0
        assert "copied" in capsys.readouterr().out

    def test_reports_failure_for_a_directory_that_is_not_a_config(self, tmp_path, capsys) -> None:
        assert main(["--config", str(tmp_path)]) == 1
        assert "no configuration.yaml" in capsys.readouterr().err

    def test_uninstall_reports_what_it_removed(self, config_dir, capsys) -> None:
        main(["--config", str(config_dir)])

        assert main(["--config", str(config_dir), "--uninstall"]) == 0
        assert "removed" in capsys.readouterr().out

    def test_uninstall_is_safe_when_nothing_is_installed(self, config_dir, capsys) -> None:
        assert main(["--config", str(config_dir), "--uninstall"]) == 0
        assert "nothing to remove" in capsys.readouterr().out
