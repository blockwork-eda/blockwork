import subprocess
from pathlib import Path
from typing import TextIO

from blockwork.executors import Invoker


class Subprocess(Invoker):
    """
    Launch invocations in a subprocess
    """

    def _launch(
        self,
        *command: str,
        workdir: Path,
        interactive: bool,
        display: bool,
        show_detach: bool,
        clear: bool,
        env: dict[str, str],
        stdout: TextIO,
        stderr: TextIO,
    ):
        workdir = self.map_to_host(workdir)
        if interactive:
            process = subprocess.Popen(command, cwd=workdir, env=env)
            process.wait()
        else:
            subprocess.run(command, stdout=stdout, stderr=stderr, cwd=workdir, env=env)
