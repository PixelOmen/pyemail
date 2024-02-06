import time
import logging
from threading import Thread, Event

import logconfig
from libs.pyemail import IMAPConn
from libs.pyemail.src.idle.idle_logging import log_info

USER = ''
PW = ''
SERVER = 'mail.roundabout.com'

def idle_handler(conn: IMAPConn, e: Event, logger: logging.Logger | None = None) -> None:
    response = conn.idle(e, idle_poll=3, logger=logger)
    log_info("Return from idle:", logger, response)
    log_info("Exiting idle thread", logger)

def main():
    e = Event()
    logconfig.init_logger(logging.DEBUG)
    logger = logging.getLogger("main")
    conn = IMAPConn(USER, PW, SERVER)
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
            conn.logout()
        except:
            pass

if __name__ == "__main__":
    main()