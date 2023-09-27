import select
import imaplib
from email import message_from_bytes
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from logging import Logger
    from threading import Event
    from email.message import Message

class Connection:
    def __init__(self, user: str, pw: str, server: str, mailbox: str="INBOX") -> None:
        self.user: str = user
        self.pw: str = pw
        self.server: str = server
        self.mailbox: str = mailbox
        self._connection: imaplib.IMAP4_SSL | None = None

    @property
    def mail(self) -> imaplib.IMAP4_SSL:
        if self._connection is None:
            self.login()
        return self._connection #type: ignore

    def login(self) -> None:
        if self._connection is not None:
            try:
                self.logout()
            except:
                pass
        self._connection = imaplib.IMAP4_SSL(self.server)
        self._connection.login(self.user, self.pw)
        self._connection.select(self.mailbox)
    
    def logout(self) -> None:
        if self._connection is None:
            return
        self._connection.logout()
        self._connection = None

    def get_ids(self, unread_only: bool=False, read_only: bool=False) -> list[str]:
        if unread_only and read_only:
            raise ValueError("Connection.get_ids: Cannot set both unread_only and read_only to True")
        elif read_only:
            search_flag = "SEEN"
        elif unread_only:
            search_flag = "UNSEEN"
        else:
            search_flag = "ALL"
        email_data: list[bytes] = self.mail.search(None, search_flag)[1]
        return [email_id.decode() for email_id in email_data[0].split()]
    
    def mark_read(self, email_id: str) -> None:
        self.mail.store(email_id, '+FLAGS', '\\Seen')

    def mark_unread(self, email_id: str) -> None:
        self.mail.store(email_id, '-FLAGS', '\\Seen')

    def get_email(self, email_id: str) -> Union["Message", None]:
        _, data = self.mail.fetch(email_id, '(RFC822)')
        if not data[0]:
            return None
        return message_from_bytes(data[0][1]) #type: ignore

    def idle(self, stopevent: "Event", tag: bytes=b"A001", logger: "Logger"=...) -> list[bytes]:
        idlecmd = tag + b" IDLE\r\n"
        self.mail.send(idlecmd)
        first_response = self.mail.readline()
        if first_response != b"+ idling\r\n":
            raise IOError(f"Didn't enter idle: {first_response}")
        unsolicted = []
        while not stopevent.is_set():
            rlist, _, _ = select.select([self.mail.sock], [], [], 1)
            if not rlist:
                continue
            unsolicted = [self.mail.readline()]
            if unsolicted[-1].startswith(b'* '):
                self.mail.send(b"DONE\r\n")
                try:
                    self._flush_for_done(tag, unsolicted, logger)
                except IOError:
                    unsolicted = []
                    try:
                        self._restart_idle_memguard(idlecmd)
                    except IOError as e:
                        if logger is not ...:
                            logger.critical(e)
                        raise e
                    else:
                        if logger is not ...:
                            logger.info("Idle restarted after memoryguard")
                    continue
                break
        return unsolicted

    def _flush_for_done(self, tag: bytes, unsolicted: list[bytes], logger: "Logger"=...) -> None:
        memoryguard = 0
        while True:
            if unsolicted[-1].startswith(tag):
                unsolicted.pop()
                break
            if memoryguard > 10:
                if logger is not ...:
                    logger.warning("pyemail.Connection.idle - Memoryguard triggered")
                    logger.debug("Unsolicted messages:")
                    for msg in unsolicted:
                        logger.debug(msg)
                raise IOError("Memoryguard triggered")
            unsolicted.append(self.mail.readline())
            memoryguard += 1

    def _restart_idle_memguard(self, idlecmd: bytes) -> None:
        while True:
            rlist, _, _ = select.select([self.mail.sock], [], [], 5)
            if not rlist:
                raise IOError("Could not restart Connection.Idle - Timeout - No response from DONE on memoryguard")
            msg = self.mail.readline()
            if msg.startswith(b'* '):
                attempts = 0
                rlist, _, _ = select.select([self.mail.sock], [], [], 5)
                while rlist is not None:
                    if attempts > 10:
                        raise IOError("Could not restart Connection.Idle - Too many messages after DONE on memoryguard")
                    self.mail.readline()
                    rlist, _, _ = select.select([self.mail.sock], [], [], 1)
                    attempts += 1
                self.mail.send(idlecmd)
                first_response = self.mail.readline()
                if first_response != b"+ idling\r\n":
                    raise IOError(f"Unable to restart idle after memoryguard - idle response: {first_response}")
                break