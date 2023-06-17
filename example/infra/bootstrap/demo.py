from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register(check_point=Path("test_file.txt"))
def demo(context : Context, last_run : datetime) -> None:
    Path("test_file.txt").write_text("hello")
