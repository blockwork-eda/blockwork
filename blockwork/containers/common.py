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
import fcntl
import os
import select
import sys
import termios
import tty
from socket import SocketIO
from threading import Event, Thread
from typing import List, Optional

@contextlib.contextmanager
def get_raw_input():
    """
    Context manager to capture raw STDIN - this uses a raw I/O stream set to be
    non-blocking in order to forward every character. Control sequences such as
    arrow keys (up/down/left/right) are multiple character sequences which means
    that reading a single character at a time is not correct. Instead, a large
    read is executed in non-blocking mode which allows these multiple character
    sequences to be captured without deadlocking.
    """
    # Capture the base configuration of termios and fcntl
    stdin        = sys.stdin.fileno()
    orig_termios = termios.tcgetattr(stdin)
    orig_fcntl   = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    # If any exception occurs, always capture it to avoid exception escaping
    try:
        # Set TTY into raw mode
        tty.setraw(stdin)
        # Set STDIN file to be non-blocking
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fcntl | os.O_NONBLOCK)
        # Yield a function to get a input
        def _get_char():
            # Use a select with a 1 second timeout to avoid infinite deadlock
            rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
            # If STDIN has data, read up to 4096 characters
            if rlist:
                return sys.stdin.read(4096)
        yield _get_char
    finally:
        # Reset termios and fcntl back to base values
        termios.tcsetattr(stdin, termios.TCSADRAIN, orig_termios)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fcntl)

def read_stream(socket : SocketIO, e_done : Event) -> Thread:
    """ Wrapped thread method to capture from the container STDOUT """
    def _inner(socket, e_done):
        try:
            # Move socket into non-blocking mode
            base = fcntl.fcntl(socket, fcntl.F_GETFL)
            fcntl.fcntl(socket, fcntl.F_SETFL, base | os.O_NONBLOCK)
            # Keep reading until done event set (or we break out)
            while not e_done.is_set():
                rlist, _, _ = select.select([socket], [], [], 1.0)
                if rlist:
                    buff = socket.read(4096)
                    if len(buff) > 0:
                        try:
                            sys.stdout.write(buff.decode("utf-8"))
                            sys.stdout.flush()
                        except UnicodeDecodeError:
                            pass
                    else:
                        break
        except BrokenPipeError:
            pass
        # Set event to signal completion of stream
        e_done.set()
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
        # Set event to signal completion of stream
        e_done.set()
    thread = Thread(target=_inner, args=(socket, e_done, command), daemon=True)
    thread.start()
    return thread
