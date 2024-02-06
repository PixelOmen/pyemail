import sys
import time
import select
import imaplib
import logging
from pathlib import Path
from typing import Callable
from dataclasses import dataclass
from threading import Thread, Event

HERE = Path(__file__).parent
ROOT = HERE.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import logconfig

USER = ''
PW = ''
SERVER = ''


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
    

def _basic_log(log_func: Callable[[str], None], msg: str,
                response: BufferResponse | None = None) -> None:
    if response:
        if msg:
            full_msg = msg + f"\n{response}"
        else:
            full_msg = str(response)
    else:
        full_msg = msg
    log_func(full_msg)

def log_debug(msg: str, logger: logging.Logger | None = None, response: BufferResponse | None = None):
    if not logger:
        return
    _basic_log(logger.debug, msg, response)

def log_info(msg: str, logger: logging.Logger | None = None, response: BufferResponse | None = None):
    if not logger:
        return
    _basic_log(logger.info, msg, response)

def log_warning(msg: str, logger: logging.Logger | None = None, response: BufferResponse | None = None):
    if not logger:
        return
    _basic_log(logger.warning, msg, response)

def log_error(msg: str, logger: logging.Logger | None = None, response: BufferResponse | None = None):
    if not logger:
        return
    _basic_log(logger.error, msg, response)

def log_critical(msg: str, logger: logging.Logger | None = None, response: BufferResponse | None = None):
    if not logger:
        return
    _basic_log(logger.critical, msg, response)



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


def idle_handler(conn: imaplib.IMAP4_SSL, e: Event, logger: logging.Logger | None = None) -> None:
    response = start_idle(conn, e, logger)
    log_info("Return from idle:", logger, response)
    log_info("Exiting idle thread", logger)


def main():
    e = Event()
    logconfig.init_logger()
    logger = logging.getLogger("main")
    conn = imaplib.IMAP4_SSL(SERVER)
    conn.login(USER, PW)
    conn.select("INBOX")
    t = Thread(target=idle_handler, args=(conn, e, logger))
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_info("Keyboard Interrupt Detected. Stopping threads", logger)
        e.set()
        t.join()
        try:
            conn.close()
            conn.logout()
        except:
            pass

if __name__ == "__main__":
    main()