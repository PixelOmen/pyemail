import imaplib
import smtplib
from pathlib import Path
from typing import TYPE_CHECKING, Union
from email import encoders, message_from_bytes
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

from .idle import start_idle

if TYPE_CHECKING:
    from logging import Logger
    from threading import Event
    from email.message import Message
    from .idle import BufferResponse


class IMAPConn:
    def __init__(self, user: str, pw: str, server: str, mailbox: str="INBOX") -> None:
        self.user: str = user
        self.pw: str = pw
        self.server: str = server
        self.mailbox: str = mailbox
        self._connection: imaplib.IMAP4_SSL | None = None

    @property
    def conn(self) -> imaplib.IMAP4_SSL:
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
        self._connection.close()
        self._connection.logout()
        self._connection = None

    def get_ids(self, unread_only: bool=False, read_only: bool=False) -> list[str]:
        if unread_only and read_only:
            raise ValueError("IMAPConn.get_ids: Cannot set both unread_only and read_only to True")
        elif read_only:
            search_flag = "SEEN"
        elif unread_only:
            search_flag = "UNSEEN"
        else:
            search_flag = "ALL"
        email_data: list[bytes] = self.conn.search(None, search_flag)[1]
        return [email_id.decode() for email_id in email_data[0].split()]
    
    def mark_read(self, email_id: str) -> None:
        self.conn.store(email_id, '+FLAGS', '\\Seen')

    def mark_unread(self, email_id: str) -> None:
        self.conn.store(email_id, '-FLAGS', '\\Seen')

    def get_email(self, email_id: str) -> Union["Message", None]:
        _, data = self.conn.fetch(email_id, '(RFC822)')
        if not data[0]:
            return None
        return message_from_bytes(data[0][1]) #type: ignore

    def idle(self, stopevent: "Event", idletag: bytes = b"A001",
             idle_poll: int = 1, logger: Union["Logger", None] = None) -> "BufferResponse":
        return start_idle(self.conn, stopevent, idle_poll, logger, idletag)



class SMTPConn:
    def __init__(self, user: str, pw: str, server: str):
        self.user = user
        self.pw = pw
        self.server = server
        self._connection: smtplib.SMTP | None = None

    @property
    def conn(self) -> smtplib.SMTP:
        if self._connection is None:
            self.login()
        return self._connection #type: ignore

    def login(self) -> None:
        if self._connection is not None:
            try:
                self.quit()
            except:
                pass
        self._connection = smtplib.SMTP(self.server, 587)
        self._connection.starttls()
        self._connection.login(self.user, self.pw)
    
    def quit(self) -> None:
        if self._connection is None:
            return
        self._connection.quit()
        self._connection = None

    def send_email(self, recipients: list[str], cc: list[str] | None = None,
                   subject: str = "", body: str = "", filepath: Path | None = None):
        msg = MIMEMultipart()
        msg['From'] = self.user
        msg['To'] = ",".join(recipients)
        if cc is not None:
            msg['Cc'] = ",".join(cc)
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        if filepath is not None:
            attachment = open(filepath, "rb")
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', "attachment; filename= %s" % filepath.name)
            msg.attach(part)
        
        text = msg.as_string()
        if cc is not None:
            all_recipients = recipients + cc
        else:
            all_recipients = recipients
        self.conn.sendmail(self.user, all_recipients, text)