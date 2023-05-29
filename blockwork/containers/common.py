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

import contextlib
import select
import sys
import termios
import tty
from socket import SocketIO
from threading import Event, Thread
from typing import List, Optional

@contextlib.contextmanager
def get_raw_input():
    """ Context manager to capture raw STDIN """
    stdin  = sys.stdin.fileno()
    before = termios.tcgetattr(stdin)
    try:
        tty.setraw(stdin)
        # TODO: There is an issue here with arrow key sequences lagging by
        #       one keypress
        def _get_char():
            rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
            if rlist:
                return sys.stdin.read(1)
            else:
                return None
        yield _get_char
    finally:
        termios.tcsetattr(stdin, termios.TCSADRAIN, before)

def read_stream(socket : SocketIO, e_done : Event) -> Thread:
    """ Wrapped thread method to capture from the container STDOUT """
    def _inner(socket, e_done):
        try:
            while not e_done.is_set():
                buff = socket.read(1)
                if len(buff) > 0:
                    try:
                        sys.stdout.write(buff.decode("utf-8"))
                        sys.stdout.flush()
                    except UnicodeDecodeError:
                        pass
                else:
                    break
            e_done.set()
        except BrokenPipeError:
            pass
    thread = Thread(target=_inner, args=(socket, e_done), daemon=True)
    thread.start()
    return thread

def write_stream(socket : SocketIO,
                 e_done : Event,
                 command : Optional[List[str]] = None) -> Thread:
    """ Wrapped thread method to capture STDIN and write into container """
    def _inner(socket, e_done, command):
        with get_raw_input() as get_char:
            try:
                if command:
                    socket._sock.send((" ".join(command) + "\n").encode("utf-8"))
                while not e_done.is_set():
                    if (char := get_char()) is not None:
                        socket._sock.send(char.encode("utf-8"))
            except BrokenPipeError:
                pass
    thread = Thread(target=_inner, args=(socket, e_done, command), daemon=True)
    thread.start()
    return thread
