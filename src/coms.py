import select
import imaplib
import smtplib
from pathlib import Path
from typing import TYPE_CHECKING, Union
from email import encoders, message_from_bytes
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

if TYPE_CHECKING:
    from logging import Logger
    from threading import Event
    from email.message import Message


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
             idle_poll: int = 1, noop_interval: int = 1800, logger: Union["Logger", None] = None) -> list[bytes]:
        idlecmd = idletag + b" IDLE\r\n"
        self.conn.send(idlecmd)
        first_response = self.conn.readline()
        if first_response != b"+ idling\r\n":
            raise IOError(f"Didn't enter idle: {first_response}")
        
        unsolicted = []
        counter = 0
        while not stopevent.is_set():
            rlist, _, _ = select.select([self.conn.sock], [], [], idle_poll)
            if not rlist:
                if counter < noop_interval:
                    counter += idle_poll
                    continue
                if logger is not None:
                    logger.debug("Connection.idle: Attempting noop")
                self.conn.send(b"DONE\r\n")
                first_response = self.conn.readline()
                if not first_response.startswith(idletag):
                    unsolicted = [first_response]
                    try:
                        self._flush_for_done(idletag, unsolicted, logger)
                    except IOError:
                        try:
                            self._restart_idle(idlecmd)
                            continue
                        except IOError as e:
                            if logger is not None:
                                logger.critical(e)
                            raise e
                else:
                    res, msg = self.conn.noop()
                    if res != "OK":
                        if logger is not None:
                            logger.critical(f"Connection.idle: NOOP failed: {msg}")
                        raise IOError(f"Connection.idle: NOOP failed: {msg}")
                    self.conn.send(idlecmd)
                    first_response = self.conn.readline()
                    if first_response != b"+ idling\r\n":
                        raise IOError(f"Connection.idle: Did not enter idle: {first_response}")
                    elif logger is not None:
                        logger.debug("Connection.idle: Idle successfuly restarted after noop")
                    counter = 0
                    continue
            
            counter = 0
            if not unsolicted:
                unsolicted = [self.conn.readline()]
            if unsolicted[-1].startswith(b'* '):
                if unsolicted[-1] == b'* BYE connection timed out\r\n':
                    if logger is not None:
                        logger.debug("Idle timed out")
                    try:
                        self._restart_idle(idlecmd)
                    except IOError as e:
                        if logger is not None:
                            logger.critical(e)
                        raise e
                    else:
                        if logger is not None:
                            logger.debug("Idle restarted after timeout")
                    continue

                self.conn.send(b"DONE\r\n")
                try:
                    self._flush_for_done(idletag, unsolicted, logger)
                except IOError:
                    unsolicted = []
                    try:
                        self._restart_idle(idlecmd)
                    except IOError as e:
                        if logger is not None:
                            logger.critical(e)
                        raise e
                    else:
                        if logger is not None:
                            logger.info("Idle restarted after memoryguard")
                    continue

                break
        return unsolicted

    def _flush_for_done(self, tag: bytes, unsolicted: list[bytes], logger: Union["Logger", None] = None) -> None:
        """
        Flushes the unsolicted messages until the DONE message is found.
        Unsolicited messages are stored in the unsolicted list passed by reference.
        """
        memoryguard = 0
        while True:
            if len(unsolicted) > 0 and unsolicted[-1].startswith(tag):
                unsolicted.pop()
                break
            if memoryguard > 1000:
                if logger is not None:
                    logger.warning("pyemail.Connection.idle - Memoryguard triggered")
                    logger.debug("Unsolicted messages:")
                    for msg in unsolicted:
                        logger.debug(msg)
                raise IOError("Memoryguard triggered")
            rlist, _, _ = select.select([self.conn.sock], [], [], 5)
            if not rlist:
                if logger is not None:
                    logger.warning("Connection._flush_for_done: Timeout - No response from server")
                raise IOError("Connection._flush_for_done: Timeout - No response from server")
            unsolicted.append(self.conn.readline())
            memoryguard += 1

    def _restart_idle(self, idlecmd: bytes) -> None:
        rlist, _, _ = select.select([self.conn.sock], [], [], 5)
        if not rlist:
            raise IOError("Could not restart Connection.Idle - No response from server")
        msg = self.conn.readline()

        # flushes any remaining messages
        if msg.startswith(b'* '):
            attempts = 0
            rlist, _, _ = select.select([self.conn.sock], [], [], 5)
            while rlist is not None:
                if attempts > 10:
                    raise IOError("Could not restart Connection.Idle - Too many messages after memoryguard DONE")
                msg = self.conn.readline()
                if msg == b'':
                    break
                rlist, _, _ = select.select([self.conn.sock], [], [], 1)
                attempts += 1

        self.login()
        self.conn.send(idlecmd)
        first_response = self.conn.readline()
        if first_response != b"+ idling\r\n":
            raise IOError(f"Unable to restart idle after memoryguard/timeout - idle response: {first_response}")





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