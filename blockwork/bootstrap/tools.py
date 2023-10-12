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
import os
from datetime import datetime
from pathlib import Path

from blockwork.tools.tool import ToolActionError

from ..context import Context
from ..foundation import Foundation
from ..tools import Tool, ToolError
from .bootstrap import Bootstrap


@Bootstrap.register()
def install_tools(context : Context, last_run : datetime) -> bool:
    """
    Run the install action for all known tools
    """
    # Get instances of all of the tools and select the default version
    all_tools = {x().default for x in Tool.get_all().values()}

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
        host_loc = tool.get_host_path(context)
        # If the tool install location already exists and install has been run
        # more recently than the definition file was updated, then skip
        if host_loc.exists():
            loc_date = datetime.fromtimestamp(host_loc.stat().st_mtime)
            def_date = datetime.fromtimestamp(tool_file.stat().st_mtime)
            if loc_date >= def_date:
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
                container = Foundation(context, hostname=f"{context.config.project}_install_{tool.id}")
                exit_code = container.invoke(context,
                                            act_def(context),
                                            readonly=False)
                if exit_code != 0:
                    raise ToolError(f"Installation of {tool_id} failed")
            else:
                logging.debug(f" - {idx}: Installation of {tool_id} produced "
                              f"a null invocation")
            logging.debug(f" - {idx}: Installation of {tool_id} succeeded")
            # Touch the install folder to ensure its datetime is updated
            try:
                os.utime(host_loc)
            except PermissionError as e:
                logging.debug(f" - Could not update modified time of {host_loc}: {e}")
                pass

