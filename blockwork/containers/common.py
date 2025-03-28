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
import json
import os
import select
import socket
import sys
import termios
import tty
from socket import SocketIO
from threading import Event, Thread
from typing import TextIO


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
    stdin = sys.stdin.fileno()
    orig_termios = termios.tcgetattr(stdin)
    orig_fcntl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    # If any exception occurs, always capture it to avoid exception escaping
    try:
        # Set TTY into raw mode
        tty.setraw(stdin)

        # Yield a function to get a input
        def _get_char() -> bytes | None:
            # Wait up to one second for data
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            # If data available
            if sys.stdin in rlist:
                # Peek at the next (up to) 4096 bytes of data
                # NOTE: This is done to reliably capture multi-character control
                #       sequences while still maintaining updates on every single
                #       key press
                data = sys.stdin.buffer.peek(4096)
                # Read as much data as was 'peeked' to move the cursor forwards
                sys.stdin.buffer.read(len(data))
                return data

        yield _get_char
    finally:
        # Reset termios and fcntl back to base values
        termios.tcsetattr(stdin, termios.TCSADRAIN, orig_termios)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fcntl)


def decode_partial_utf8(buffer: bytes, errors: str = "strict") -> tuple[str, bytes]:
    """
    Detect if the bytes sequence ends mid-way through a multi-byte unicode
    character, and if so decode up to that point, returning the decoded
    unicode string and the remaining undecoded bytes.

    See:
    https://www.ibm.com/docs/en/db2/11.5?topic=support-unicode-character-encoding#c0004816__utf8utf16
    """
    if len(buffer) > 0 and (buffer[-1] & 0b1100_0000) == 0b1100_0000:
        # Last byte is start of a multi-byte sequence
        complete, partial = buffer[:-1], buffer[-1:]
    elif len(buffer) > 1 and ((buffer[-2] & 0b1110_0000) == 0b1110_0000):
        # Second to last byte is start of a three or four byte sequence
        complete, partial = buffer[:-2], buffer[-2:]
    elif len(buffer) > 2 and ((buffer[-3] & 0b1111_0000) == 0b1111_0000):
        # Third to last byte is start of a four byte sequence
        complete, partial = buffer[:-3], buffer[-3:]
    else:
        complete, partial = buffer, b""
    return complete.decode("utf-8", errors), partial


def read_stream(socket: SocketIO, stdout: TextIO, e_done: Event) -> Thread:
    """Wrapped thread method to capture from the container STDOUT"""

    def _inner(socket, e_done):
        try:
            # Move socket into non-blocking mode
            base = fcntl.fcntl(socket, fcntl.F_GETFL)
            fcntl.fcntl(socket, fcntl.F_SETFL, base | os.O_NONBLOCK)
            # Keep track of partial unicode characters
            partial_bytes = b""
            # Keep reading until done event set (or we break out)
            while not e_done.is_set():
                rlist, _, _ = select.select([socket], [], [], 0.1)
                if rlist:
                    buff = socket.read(1024)
                    string, partial_bytes = decode_partial_utf8(partial_bytes + buff)

                    if len(buff):
                        stdout.write(string)
                        stdout.flush()
                    else:
                        # If there are remaining partial bytes, this will except
                        partial_bytes.decode("utf-8", errors="strict")
                        break
        except BrokenPipeError:
            pass
        # Set event to signal completion of stream
        e_done.set()

    thread = Thread(target=_inner, args=(socket, e_done), daemon=True)
    thread.start()
    return thread


def write_stream(
    socket: SocketIO, e_done: Event, e_interacted: Event, command: list[str] | None = None
) -> Thread:
    """Wrapped thread method to capture STDIN and write into container"""
    # Format Effector escape bytes can be ignored for detecting user
    # interaction.
    fe_escape_byte = bytes([0x1B])

    def _inner(socket, e_done, command):
        with get_raw_input() as get_char:
            try:
                # Send the initial command sequence
                if command:
                    socket._sock.send((" ".join(command) + "\n").encode("utf-8"))
                # Monitor for further STDIO
                while not e_done.is_set():
                    if (char := get_char()) is not None:
                        socket._sock.send(char)
                        if not char.startswith(fe_escape_byte):
                            # Detected user interaction
                            e_interacted.set()
            except BrokenPipeError:
                pass
        # Set event to signal completion of stream
        e_done.set()

    thread = Thread(target=_inner, args=(socket, e_done, command), daemon=True)
    thread.start()
    return thread


def forwarding_host(e_done: Event) -> tuple[Thread, int]:
    """
    Wrapped thread method to handle forwarded commands from the container. Within
    the container, a relatively simple Python script encapsulates calls to the
    'blockwork' command in a JSON dictionary and forwards them to the socket
    exposed by this thread. This thread is then responsible for enacting the
    request and sending the response back to the socket. The sockets are
    implemented in a simple fashion so as to add few requirements to the Python
    installation within the container. All argument handling is performed by the
    host process.

    :param e_done:  Event that signals when container has finished
    :returns:       Tuple of the launched thread and the port number
    """
    # Choose a port number
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]

    # Declare the thread process
    def _inner(e_done, port):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", port))
            s.settimeout(0.2)
            s.listen()
            # Keep looping until container stops
            while not e_done.is_set():
                try:
                    conn, _addr = s.accept()
                except TimeoutError:
                    continue
                # Once a client connects, start receiving data
                with conn:
                    conn.setblocking(0)
                    conn.settimeout(0.2)
                    buffer = bytearray()
                    # The first 4 bytes carry the data size
                    while not e_done.is_set() and len(buffer) < 4:
                        buffer += conn.recv(4 - len(buffer))
                    # If done event set, break out
                    if e_done.is_set():
                        break
                    size = sum([(int(x) << (i * 8)) for i, x in enumerate(buffer)])
                    # The remaining data is encoded JSON
                    raw_data = conn.recv(size)
                    # Decode JSON
                    try:
                        data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        print("Decoding error in forwarded command")
                        break
                    # TODO: DO SOMETHING WITH DATA!
                    # Encode response
                    raw_resp = json.dumps(
                        {
                            "stdout": f"STDOUT for {data}",
                            "stderr": f"STDERR for {data}",
                            "exitcode": 1,
                        }
                    ).encode("utf-8")
                    # Send the data size as the first 4 bytes
                    conn.sendall(bytearray(((len(raw_resp) >> (x * 8)) & 0xFF) for x in range(4)))
                    # Send the encoded data
                    conn.sendall(raw_resp)

    # Start the thread
    thread = Thread(target=_inner, args=(e_done, port), daemon=True)
    thread.start()
    # Return thread and port number
    return thread, port
