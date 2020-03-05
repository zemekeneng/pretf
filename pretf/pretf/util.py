import os
import shlex
import sys
from contextlib import contextmanager
from fnmatch import fnmatch
from importlib.abc import Loader
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path, PurePath
from subprocess import PIPE, CalledProcessError, CompletedProcess, Popen
from threading import Thread
from types import ModuleType
from typing import BinaryIO, Generator, List, Optional, Sequence, TextIO, Tuple, Union

from . import log


def execute(
    file: str, args: Sequence[str], env: Optional[dict] = None, verbose: bool = True
) -> CompletedProcess:
    """
    Executes a command and waits for it to finish.

    If args are provided, then they will be used.

    If args are not provided, and arguments were used to run this program,
    then those arguments will be used.

    If args are not provided, and no arguments were used to run this program,
    and default args are provided, then they will be used.

    Returns the exit code from the command that is run.

    """

    if env is None:
        env = os.environ.copy()

    if verbose:
        log.ok(f"run: {' '.join(shlex.quote(arg) for arg in args)}")

    if env.get("PRETF_CAPTURE_OUTPUT"):
        return _execute_and_capture(file, args, env)
    else:
        return _execute(file, args, env)


def _execute(file: str, args: Sequence[str], env: dict) -> CompletedProcess:

    proc = Popen(args, executable=file, env=env)

    returncode = proc.wait()

    if returncode != 0:
        raise CalledProcessError(
            returncode=returncode, cmd=" ".join(shlex.quote(arg) for arg in args),
        )

    return CompletedProcess(args=args, returncode=returncode,)


def _execute_and_capture(file: str, args: Sequence[str], env: dict) -> CompletedProcess:

    stdout_buffer = StringIO()
    stderr_buffer = StringIO()

    proc = Popen(args, executable=file, stdout=PIPE, stderr=PIPE, env=env)

    stdout_thread = Thread(
        target=_fan_out, args=(proc.stdout, sys.stdout, stdout_buffer)
    )
    stdout_thread.start()

    stderr_thread = Thread(
        target=_fan_out, args=(proc.stderr, sys.stderr, stderr_buffer)
    )
    stderr_thread.start()

    returncode = proc.wait()

    stdout_thread.join()
    stderr_thread.join()

    stdout_buffer.seek(0)
    stderr_buffer.seek(0)

    if returncode != 0:
        raise CalledProcessError(
            returncode=returncode,
            cmd=" ".join(shlex.quote(arg) for arg in args),
            output=stdout_buffer.read(),
            stderr=stderr_buffer.read(),
        )

    return CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout_buffer.read(),
        stderr=stderr_buffer.read(),
    )


def _fan_out(input_steam: BinaryIO, *output_streams: TextIO) -> None:
    while True:
        char = input_steam.read(1).decode()
        if char:
            for output_stream in output_streams:
                output_stream.write(char)
        else:
            break


def find_paths(
    path_patterns: Sequence[str],
    exclude_name_patterns: Sequence[str] = [],
    cwd: Optional[Union[Path, str]] = None,
) -> Generator[Path, None, None]:

    if cwd is None:
        cwd = Path.cwd()
    elif isinstance(cwd, str):
        cwd = Path(cwd)

    for pattern in path_patterns:
        for path in cwd.glob(pattern):
            for exclude_name_pattern in exclude_name_patterns:
                if fnmatch(path.name, exclude_name_pattern):
                    break
            else:
                yield path


def find_workflow_path() -> Optional[Path]:
    for name in ("pretf.workflow.py", "pretf.py"):

        path = Path.cwd() / name
        if path.exists():
            return path

        for dir_path in path.parents:
            path = dir_path / name
            if path.exists():
                return path

    return None


@contextmanager
def import_file(path: Union[PurePath, str]) -> Generator[ModuleType, None, None]:
    """
    Imports a Python module from any local filesystem path.
    Temporarily alters sys.path to allow the imported module
    to import other modules in the same directory.

    """

    pathdir = os.path.dirname(path)
    if pathdir in sys.path:
        added_to_sys_path = False
    else:
        sys.path.insert(0, pathdir)
        added_to_sys_path = True
    try:
        name = os.path.basename(path).split(".")[0]
        spec = spec_from_file_location(name, str(path))
        module = module_from_spec(spec)
        assert isinstance(spec.loader, Loader)
        loader: Loader = spec.loader
        try:
            loader.exec_module(module)
        except Exception as error:
            log.bad(error)
            raise
        yield module
    finally:
        if added_to_sys_path:
            sys.path.remove(pathdir)


def parse_args() -> Tuple[Optional[str], List[str], List[str], str]:

    cmd = ""
    args = []
    flags = []

    help_flags = set(("-h", "-help", "--help"))
    version_flags = set(("-v", "-version", "--version"))

    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            if not cmd and arg in help_flags:
                cmd = "help"
            elif not cmd and arg in version_flags:
                cmd = "version"
            else:
                flags.append(arg)
        elif not cmd:
            cmd = arg
        else:
            args.append(arg)

    config_dir = ""
    if cmd == "apply":
        if args:
            dir_or_plan = args[0]
            if os.path.isdir(dir_or_plan):
                config_dir = dir_or_plan
    elif cmd == "force-unlock":
        if len(args) == 2:
            config_dir = args[1]
    elif cmd in {
        "console",
        "destroy",
        "get",
        "graph",
        "init",
        "plan",
        "refresh",
        "validate",
    }:
        if args:
            config_dir = args[-1]

    return (cmd, args, flags, config_dir)
