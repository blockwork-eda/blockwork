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

from datetime import datetime

from rich.console import Console

from ..context import Context
from ..foundation import Foundation
from .bootstrap import Bootstrap


@Bootstrap.register()
def build_foundation(context: Context, last_run: datetime) -> bool:
    """
    Built-in bootstrap action that builds the foundation container using the
    active runtime.
    """
    with Console().status("Building container...", spinner="arc"):
        Foundation(context).build()
        return True
