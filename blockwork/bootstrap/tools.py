# Copyright 2023, Blockwork, github.com/intuity/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import logging
from datetime import datetime
from pathlib import Path

from ordered_set import OrderedSet as OSet

from ..context import Context
from ..foundation import Foundation
from ..tools import Tool, ToolError
from ..tools.tool import ToolActionError
from .bootstrap import Bootstrap


@Bootstrap.register()
def install_tools(context: Context, last_run: datetime) -> bool:
    """
    Run the install action for all known tools
    """
    # Get instances of all of the tools and install all specified versions
    all_tools = OSet([])
    for tool in Tool.get_all().values():
        for version in tool.versions:
            all_tools.add(version)

    # Order by requirements
    resolved = []
    last_len = len(all_tools)
    logging.debug(f"Ordering {len(all_tools)} tools based on requirements:")
    while all_tools:
        for tool in all_tools:
            if len(set(tool.resolve_requirements()).difference(resolved)) == 0:
                logging.debug(f" - {len(resolved)}: {' '.join(tool.id_tuple)}")
                resolved.append(tool)
        all_tools = all_tools - set(resolved)
        if len(all_tools) == last_len:
            raise ToolError("Deadlock detected resolving tool requirements")
        last_len = len(all_tools)

    # Install in order
    logging.info(f"Installing {len(resolved)} tools:")
    for idx, tool in enumerate(resolved):
        tool_id = " ".join(tool.id_tuple)
        tool_file = Path(inspect.getfile(type(tool.tool)))
        host_loc = tool.tool.get_host_path(context, absolute=False)
        # Ensure the parent of the tool's folder exists
        host_loc.parent.mkdir(exist_ok=True, parents=True)
        # Select a touch file location, this is used to determine if the tool
        # installation is up to date
        touch_file = context.host_state / "tools" / tool.tool.name / tool.version / Tool.TOUCH_FILE
        touch_file.parent.mkdir(exist_ok=True, parents=True)
        # If the touch file exists and install has been run more recently than
        # the definition file was updated, then skip
        if touch_file.exists():
            tch_date = datetime.fromtimestamp(touch_file.stat().st_mtime)
            def_date = datetime.fromtimestamp(tool_file.stat().st_mtime)
            if tch_date >= def_date:
                logging.debug(f" - {idx}: Tool {tool_id} is already installed")
                continue
        # Attempt to install
        try:
            act_def = tool.get_action("installer")
        except ToolActionError:
            logging.debug(f" - {idx}: Tool {tool_id} does not define an install action")
        else:
            logging.info(f" - {idx}: Launching installation of {tool_id}")
            invk = act_def(context)
            if invk is not None:
                container = Foundation(
                    context, hostname=f"{context.config.project}_install_{tool.id}"
                )
                exit_code = container.invoke(context, act_def(context), readonly=False).exit_code
                if exit_code != 0:
                    raise ToolError(f"Installation of {tool_id} failed")
            else:
                logging.debug(f" - {idx}: Installation of {tool_id} produced a null invocation")
            logging.debug(f" - {idx}: Installation of {tool_id} succeeded")
            # Touch the install folder to ensure its datetime is updated
            try:
                touch_file.touch()
            except PermissionError as e:
                logging.debug(f" - Could not update modified time of {touch_file}: {e}")
                pass
