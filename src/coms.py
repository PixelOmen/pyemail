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
        self._connection = imaplib.IMAP4_SSL(self.server)
        self._connection.login(self.user, self.pw)
        self._connection.select(self.mailbox)
    
    def logout(self) -> None:
        if self._connection is None:
            return
        self._connection.logout()
        self._connection = None

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
                memoryguard = 0
                try:
                    while True:
                        if unsolicted[-1].startswith(tag):
                            unsolicted.pop()
                            break
                        if memoryguard > 100:
                            if logger is not ...:
                                logger.warning("pyemail.Connection.idle - Memoryguard triggered")
                                logger.warning("Unsolicted messages:")
                                for msg in unsolicted:
                                    logger.warning(msg)
                            raise IOError("Memoryguard triggered")
                        unsolicted.append(self.mail.readline())
                        memoryguard += 1
                except IOError:
                    unsolicted = []
                    continue
                break
        return unsolicted

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
