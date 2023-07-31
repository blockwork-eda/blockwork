import json
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib import request

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register(check_point=Path("infra/tools/urls.json"))
def download_tools(context : Context, last_run : datetime) -> bool:
    # Get the content of the tool URL JSON file
    tool_urls = context.host_root / "infra" / "tools" / "urls.json"
    with tool_urls.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Define a custom closure to preserve permissions
    def _extract(zh, info, extract_dir):
        zh.extract(info.filename, path=extract_dir)
        (Path(extract_dir) / info.filename).chmod(info.external_attr >> 16)
    # Download and unzip all of the tools
    tool_base = context.host_root.parent / f"{context.config.project}.tools"
    tool_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, (rel_path, url) in enumerate(data.items()):
            if (tool_base / rel_path).exists():
                logging.info(f"[{idx:2d} / {len(data.keys()):2d}] Skipping as {rel_path} already exists")
                continue
            local = Path(tmpdir) / f"tool_{idx}.zip"
            logging.info(f"[{idx:2d} / {len(data.keys()):2d}] Downloading {rel_path} from {url}")
            request.urlretrieve(url, local)
            logging.info(f"[{idx:2d} / {len(data.keys()):2d}] Unzipping {rel_path} into {tool_base}")
            with zipfile.ZipFile(local, "r") as zh:
                for info in zh.infolist():
                    _extract(zh, info, tool_base)
    # Return False to indicate this step was not up-to-date
    return False
