import imaplib
from email import message_from_bytes
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
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

    def get_ids(self, unread: bool=False) -> list[str]:
        search_flag = "UNSEEN" if unread else "ALL"
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
