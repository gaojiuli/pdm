import functools
import os
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from pdm.cli import actions, commands
from pdm.models.requirements import parse_requirement
from pdm.utils import get_python_version


@pytest.fixture()
def invoke():
    runner = CliRunner()
    return functools.partial(runner.invoke, commands.cli)


def test_help_option(invoke):
    result = invoke(["--help"])
    assert "PDM - Python Development Master" in result.output


def test_lock_command(project, invoke, mocker):
    m = mocker.patch.object(actions, "do_lock")
    invoke(["lock"], obj=project)
    m.assert_called_with(project)


def test_install_command(project, invoke, mocker):
    do_lock = mocker.patch.object(actions, "do_lock")
    do_sync = mocker.patch.object(actions, "do_sync")
    invoke(["install"], obj=project)
    do_lock.assert_called_once()
    do_sync.assert_called_once()


def test_sync_command(project, invoke, mocker):
    do_sync = mocker.patch.object(actions, "do_sync")
    invoke(["sync"], obj=project)
    do_sync.assert_called_once()


def test_update_command(project, invoke, mocker):
    do_update = mocker.patch.object(actions, "do_update")
    invoke(["update"], obj=project)
    do_update.assert_called_once()


def test_remove_command(project, invoke, mocker):
    do_remove = mocker.patch.object(actions, "do_remove")
    invoke(["remove", "demo"], obj=project)
    do_remove.assert_called_once()


def test_add_command(project, invoke, mocker):
    do_add = mocker.patch.object(actions, "do_add")
    invoke(["add", "requests"], obj=project)
    do_add.assert_called_once()


def test_build_command(project, invoke, mocker):
    do_build = mocker.patch.object(actions, "do_build")
    invoke(["build"], obj=project)
    do_build.assert_called_once()


def test_list_command(project, invoke, mocker):
    do_list = mocker.patch.object(actions, "do_list")
    invoke(["list"], obj=project)
    do_list.assert_called_once()


def test_info_command(project, invoke):
    result = invoke(["info"], obj=project)
    assert "Project Root:" in result.output
    assert project.root.as_posix() in result.output

    result = invoke(["info", "--python"], obj=project)
    assert result.output.strip() == project.environment.python_executable

    result = invoke(["info", "--project"], obj=project)
    assert result.output.strip() == project.root.as_posix()

    result = invoke(["info", "--env"], obj=project)
    assert result.exit_code == 0


def test_run_command(invoke, capfd):
    result = invoke(["run", "python", "-c", "import halo;print(halo.__file__)"])
    assert result.exit_code == 0
    assert os.sep.join(["pdm", "__pypackages__"]) in capfd.readouterr()[0]


def test_run_command_not_found(invoke):
    result = invoke(["run", "foobar"])
    assert result.exit_code == 2
    assert "Error: Command 'foobar' is not found on your PATH." in result.output


def test_run_pass_exit_code(invoke):
    result = invoke(["run", "python", "-c", "1/0"])
    assert result.exit_code == 1


def test_uncaught_error(invoke, mocker):
    mocker.patch.object(actions, "do_list", side_effect=RuntimeError("test error"))
    result = invoke(["list"])
    assert "RuntimeError: test error" in result.output

    result = invoke(["list", "-v"])
    assert isinstance(result.exception, RuntimeError)


def test_use_command(project, invoke):
    python_path = Path(shutil.which("python")).as_posix()
    result = invoke(["use", "-f", "python"], obj=project)
    assert result.exit_code == 0
    config_content = project.root.joinpath(".pdm.toml").read_text()
    assert python_path in config_content

    result = invoke(["use", "-f", python_path], obj=project)
    assert result.exit_code == 0

    project.tool_settings["python_requires"] = ">=3.6"
    project.write_pyproject()
    result = invoke(["use", "2.7"], obj=project)
    assert result.exit_code == 1


def test_use_python_by_version(project, invoke):
    python_version = ".".join(map(str, sys.version_info[:2]))
    result = invoke(["use", "-f", python_version], obj=project)
    assert result.exit_code == 0


def test_install_with_lockfile(project, invoke, working_set, repository):
    result = invoke(["lock"], obj=project)
    assert result.exit_code == 0
    result = invoke(["install"], obj=project)
    assert "Lock file" not in result.output

    project.add_dependencies({"pytz": parse_requirement("pytz")})
    result = invoke(["install"], obj=project)
    assert "Lock file hash doesn't match" in result.output
    assert "pytz" in project.get_locked_candidates()
    assert project.is_lockfile_hash_match()


def test_init_command(project_no_init, invoke, mocker):
    mocker.patch(
        "pdm.cli.commands.get_user_email_from_git",
        return_value=("Testing", "me@example.org"),
    )
    do_init = mocker.patch.object(actions, "do_init")
    result = invoke(
        ["init"], input="python\ntest-project\n\n\n\n\n\n", obj=project_no_init
    )
    print(result.output)
    assert result.exit_code == 0
    python_version = ".".join(
        map(str, get_python_version(project_no_init.environment.python_executable)[:2])
    )
    do_init.assert_called_with(
        project_no_init,
        "test-project",
        "0.0.0",
        "MIT",
        "Testing",
        "me@example.org",
        f">={python_version}",
    )


def test_config_command(project, invoke):
    result = invoke(["config"], obj=project)
    assert result.exit_code == 0
    assert "python.use_pyenv = True" in result.output

    result = invoke(["config", "-v"], obj=project)
    assert result.exit_code == 0
    assert "Use the pyenv interpreter" in result.output


def test_config_get_command(project, invoke):
    result = invoke(["config", "get", "python.use_pyenv"], obj=project)
    assert result.exit_code == 0
    assert result.output.strip() == "True"

    result = invoke(["config", "get", "foo.bar"], obj=project)
    assert result.exit_code != 0


def test_config_set_command(project, invoke):
    result = invoke(["config", "set", "python.use_pyenv", "false"], obj=project)
    assert result.exit_code == 0
    result = invoke(["config", "get", "python.use_pyenv"], obj=project)
    assert result.output.strip() == "False"

    result = invoke(["config", "set", "foo.bar"], obj=project)
    assert result.exit_code != 0


def test_config_project_global_precedence(project, invoke):
    invoke(["config", "set", "cache_dir", "/path/to/foo"], obj=project)
    invoke(["config", "set", "-l", "cache_dir", "/path/to/bar"], obj=project)

    result = invoke(["config", "get", "cache_dir"], obj=project)
    assert result.output.strip() == "/path/to/bar"


def test_cache_clear_command(project, invoke, mocker):
    m = mocker.patch("shutil.rmtree")
    result = invoke(["cache", "clear"], obj=project)
    assert result.exit_code == 0
    m.assert_called_once()
