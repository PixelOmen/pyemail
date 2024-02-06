import email
import imaplib
from dataclasses import dataclass
from dateutil.parser import parse as dateparser

@dataclass
class EmailInfo:
    date: str
    sender: str
    recipients: str
    body: str

def fetch_emails(username: str, password: str, server: str, mailbox: str, count: int) -> list[EmailInfo]:
    """
    Fetch emails from the specified mailbox using IMAP protocol.

    Args:
    username (str): The email account username.
    password (str): The email account password.
    server (str): The IMAP server address.
    mailbox (str): The mailbox to fetch emails from.

    Returns:
    list[Email]: A list of Email objects.
    """

    mail = imaplib.IMAP4_SSL(server)
    mail.login(username, password)
    mail.select(mailbox)

    result, data = mail.uid('search', 'CHARSET', 'UTF-8', 'ALL')
    emailids = data[0].split()[::-1][:count]

    emails = []
    for uid in emailids:
        result, data = mail.uid('fetch', uid, '(RFC822)')
        raw_email = data[0][1].decode('utf-8')
        email_message = email.message_from_string(raw_email)

        date_str = email_message['Date']
        parsed_date = dateparser(date_str)
        date = parsed_date.strftime('%Y-%m-%d %H:%M:%S%z')

        sender = email_message['From']
        recipients = email_message['To']
        body = ''

        if email_message.is_multipart():
            for part in email_message.walk():
                part_content_type = part.get_content_type()
                if part_content_type == 'text/plain':
                    charset = part.get_content_charset()
                    if charset is None:
                        charset = 'utf-8'
                    body += part.get_payload(decode=True).decode(charset, errors='replace') #type: ignore
        else:
            body = email_message.get_payload(decode=True).decode('utf-8') #type: ignore

        email_obj = EmailInfo(date, sender, recipients, body)
        emails.append(email_obj)

    mail.close()
    mail.logout()

    return emails