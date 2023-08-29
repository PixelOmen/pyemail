from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
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
        self._message: Union[Message, None] = None
        self._pulled: bool = False

    @property
    def exists(self) -> bool:
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
    
    def _parse_msg(self) -> None:
        if not self.exists:
            return
        self.recipients = self.message.get_all('To', [])
        self.sender = self.message.get('From', "")
        self.subject = self.message.get('Subject', "")
        self.body = self.message.get_payload(decode=True).decode("utf-8").replace("\r\n", "\n")

    def pull(self, retry: bool=False) -> None:
        if self._pulled and not retry:
            return
        self._message = self.connection.get_email(self.id)
        self._pulled = True
        if self._message is not None:
            self._parse_msg()

    def mark_read(self) -> None:
        self.connection.mark_read(self.id)
