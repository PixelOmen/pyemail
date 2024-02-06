from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    import logging
    from .core import BufferResponse


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