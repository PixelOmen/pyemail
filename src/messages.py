import email.utils
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from datetime import datetime
    from .coms import Connection, Message

class PyMsg:
    def __init__(self, id: str, con: "Connection") -> None:
        self.id = id
        if not self.id.isdigit():
            raise ValueError("Email ID must be a number")
        self.connection = con
        self.recipients = []
        self.sender = ""
        self.subject = ""
        self.body = ""
        self.deleted: bool = False
        self._rawdate = ""
        self._date: datetime | None = None
        self._message: Union["Message", None] = None
        self._pulled: bool = False

    @property
    def exists(self) -> bool:
        if self.deleted:
            return False
        if self._message is not None:
            return True
        if self._pulled and self._message is None:
            return False
        self.pull()
        return False if self._message is None else True
    
    @property
    def message(self) -> "Message":
        if not self.exists:
            raise ValueError(f"Email does not exist - {self.id}")
        return self._message #type: ignore

    @property
    def date(self) -> "datetime":
        if self._date is not None:
            return self._date
        if not self.exists:
            raise ValueError(f"Email does not exist - {self.id}")
        self._date = email.utils.parsedate_to_datetime(self._rawdate).replace(tzinfo=None)
        return self._date
    
    def _parse_msg(self) -> None:
        if not self.exists:
            return
        self.recipients = [str(result) for result in self.message.get_all('To', [])]
        self.sender = str(self.message.get('From', ""))
        self.subject = str(self.message.get('Subject', ""))
        self._rawdate = str(self.message.get('Date', ""))
        body = None
        if self.message.is_multipart():
            for part in self.message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and 'attachment' not in content_disposition:
                    raw = part.get_payload(decode=True)
                    body = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
                    break
        else:
            raw = self.message.get_payload(decode=True)
            body = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
            
        if body is None:
            self.body = ""
        else:
            self.body = body

    def pull(self, retry: bool=False) -> None:
        if self._pulled and not retry:
            return
        self._message = self.connection.get_email(self.id)
        self._pulled = True
        if self._message is not None:
            self._parse_msg()

    def mark_read(self) -> None:
        self.connection.mark_read(self.id)

    def mark_unread(self) -> None:
        self.connection.mark_unread(self.id)

    def delete(self) -> None:
        self.connection.mail.store(self.id, '+FLAGS', '\\Deleted')
        self.connection.mail.expunge()
        self.deleted = True
