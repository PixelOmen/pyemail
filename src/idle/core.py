import select
from typing import TYPE_CHECKING
from dataclasses import dataclass

from .idle_logging import log_debug, log_info, log_critical, log_warning, log_error

if TYPE_CHECKING:
    import logging
    import imaplib
    from threading import Event
    from .core import BufferResponse

@dataclass
class BufferResponse:
    buffer: bytes
    lines: list[bytes]

    def __str__(self):
        buffer = f"Buffer: {self.buffer}"
        if self.lines:
            buffer += "\n"
        else:
            return buffer
        lines = "\n".join([f"Line: {line}" for line in self.lines])
        return buffer + lines
    
    def is_empty(self):
        return not self.buffer and not self.lines


def read_buffer(conn: imaplib.IMAP4_SSL, size: int, timeout: int=1) -> BufferResponse:
    lines = []
    buffer = b""
    current_timeout = timeout
    while True:
        ready_to_read, _, _ = select.select([conn.sock], [], [], current_timeout)
        if not ready_to_read:
            break

        current_timeout = 0.5
        data = conn.sock.recv(size)
        buffer += data

        while b"\r\n" in buffer:
            line, buffer = buffer.split(b"\r\n", 1)
            lines.append(line)

    return BufferResponse(buffer, lines)

def idle_success(res: BufferResponse) -> bool:
    if b"+ idling" in res.buffer:
        return True
    for line in res.lines:
        if b"+ idling" in line:
            return True
    return False

def idle_terminated(res: BufferResponse, tag: bytes) -> bool:
    term_msg = tag + b" OK IDLE terminated"
    if term_msg in res.buffer:
        return True
    for line in res.lines:
        if term_msg in line:
            return True
    return False

def idle_timeout(res: BufferResponse) -> bool:
    timeout_msg = b'* BYE '
    if timeout_msg in res.buffer:
        return True
    for line in res.lines:
        if timeout_msg in line:
            return True
    return False

def start_idle(conn: imaplib.IMAP4_SSL, e: Event,
         logger: logging.Logger | None = None, tag: bytes = b"A001") -> BufferResponse:
    idlecmd = tag + b" IDLE\r\n"
    is_idle = False
    emtpy_response = BufferResponse(b"", [])

    while not e.is_set():
        if not is_idle:
            conn.send(idlecmd)
            response = read_buffer(conn, 4096, timeout=3)
            if idle_success(response):
                is_idle = True
                log_info("IDLE Success", logger)
            else:
                log_critical("IDLE Failed", logger, response)
                break

        response = read_buffer(conn, 4096, timeout=3)
        if idle_timeout(response):
            is_idle = False
            log_warning("IDLE Timeout, attempting new IDLE", logger)
            continue
        if idle_terminated(response, tag):
            is_idle = False
            log_critical("IDLE Unexpectedly Terminated", logger)
            return response
        
        if not response.is_empty():
            return response

    if is_idle:
        conn.send(b"DONE\r\n")
        response = read_buffer(conn, 4096, timeout=3)
        if idle_terminated(response, tag):
            log_info("IDLE Terminated on event", logger)
        else:
            log_error("IDLE not terminated on event", logger, response)
        return response
    return emtpy_response