from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register(check_point=Path("test_file.txt"))
def demo(context : Context, last_run : datetime) -> bool:
    Path("test_file.txt").write_text("hello")
    # Return False to indicate this step was not up-to-date
    return False
