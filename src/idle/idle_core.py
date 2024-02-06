import select
from dataclasses import dataclass
from typing import TYPE_CHECKING, Union
from datetime import datetime, timedelta

from .idle_logging import log_debug, log_critical, log_warning, log_error

if TYPE_CHECKING:
    import logging
    import imaplib
    from threading import Event

BUFFER_SIZE = 4096


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


def _read_buffer(conn: "imaplib.IMAP4_SSL", size: int, timeout: int=1) -> BufferResponse:
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

def _idle_success(res: BufferResponse) -> bool:
    if b"+ idling" in res.buffer:
        return True
    for line in res.lines:
        if b"+ idling" in line:
            return True
    return False

def _idle_terminated(res: BufferResponse, tag: bytes) -> bool:
    term_msg = tag + b" OK IDLE terminated"
    if term_msg in res.buffer:
        return True
    for line in res.lines:
        if term_msg in line:
            return True
    return False

def _idle_timeout(res: BufferResponse) -> bool:
    timeout_msg = b'* BYE '
    if timeout_msg in res.buffer:
        return True
    for line in res.lines:
        if timeout_msg in line:
            return True
    return False

def _timer_up(start_time: datetime, timer: timedelta) -> bool:
    current_time = datetime.now()
    if current_time >= start_time + timer:
        return True
    return False

def start_idle(conn: "imaplib.IMAP4_SSL", e: "Event", buffer_timeout: int = 3, refresh_idle: int = 0,
                logger: Union["logging.Logger", None] = None, tag: bytes = b"A001") -> BufferResponse:
    """
    Sends an `IDLE` command to the IMAP server.
    `IDLE` is terminated after recieving unsolicated responses from the server or Event `e` has been set.
    If `refresh_idle` is not 0, `IDLE` will terminate and restart every number of minutes equal to its value.
    """
    if refresh_idle < 0:
        raise ValueError("`refresh_idle` cannot be less than 0")
    if buffer_timeout < 1:
        raise ValueError("`buffer_timeout` cannot be less than 1")
    idlecmd = tag + b" IDLE\r\n"
    is_idle = False
    start_time = datetime.now()
    timer = timedelta(minutes=refresh_idle)
    response = BufferResponse(b"", [])


    while not e.is_set():
        if is_idle and refresh_idle > 0 and _timer_up(start_time, timer):
            is_idle = False
            start_time = datetime.now()
            conn.send(b"DONE\r\n")
            response = _read_buffer(conn, BUFFER_SIZE, timeout=buffer_timeout)
            if _idle_terminated(response, tag):
                log_debug("IDLE refresh triggered", logger)
            else:
                log_error("IDLE not terminated properly on refresh, attempting restart", logger, response)
            continue
        
        if not is_idle:
            conn.send(idlecmd)
            response = _read_buffer(conn, BUFFER_SIZE, timeout=buffer_timeout)
            if _idle_success(response):
                is_idle = True
                log_debug("IDLE Success", logger)
            else:
                log_critical("IDLE Failed", logger, response)
                break

        response = _read_buffer(conn, BUFFER_SIZE, timeout=buffer_timeout)
        if _idle_timeout(response):
            is_idle = False
            start_time = datetime.now()
            log_warning("IDLE timeout, attempting new IDLE", logger)
            continue
        if _idle_terminated(response, tag):
            is_idle = False
            start_time = datetime.now()
            log_critical("IDLE unexpectedly terminated, attempting restart", logger)
            continue
        
        if not response.is_empty():
            log_debug("Unsolicited response:", logger, response)
            conn.send(b"DONE\r\n")
            done_response = _read_buffer(conn, BUFFER_SIZE, timeout=buffer_timeout)
            if _idle_terminated(done_response, tag):
                log_debug("IDLE terminated on unsolicited response", logger)
            else:
                log_error("IDLE not terminated properly on unsolicited response", logger, done_response)
            return response

    if is_idle:
        conn.send(b"DONE\r\n")
        response = _read_buffer(conn, BUFFER_SIZE, timeout=buffer_timeout)
        if _idle_terminated(response, tag):
            log_debug("IDLE Terminated on event", logger)
        else:
            log_error("IDLE not terminated on event", logger, response)
        return response
    return BufferResponse(b"", [])