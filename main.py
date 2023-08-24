import imaplib

SERVER = "mail.roundabout.com"
USER = "eacosta@roundabout.com"
PASS = "Lancealot!1234"

def login(mailbox: str="INBOX") -> imaplib.IMAP4_SSL:
    mail = imaplib.IMAP4_SSL(SERVER)
    mail.login(USER, PASS)
    mail.select(mailbox)
    return mail

def get_unread(mail: imaplib.IMAP4_SSL) -> list[str]:
    email_data: list[bytes] = mail.search(None, 'UNSEEN')[1]
    return [email_id.decode() for email_id in email_data[0].split()]

def mark_read(email_id: str, mail: imaplib.IMAP4_SSL) -> None:
    mail.store(email_id, '+FLAGS', '\\Seen')

mail = login()
unread = get_unread(mail)
for email_id in unread:
    mark_read(email_id, mail)
mail.logout()