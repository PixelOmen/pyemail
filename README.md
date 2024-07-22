
# pyemail

## Overview
**pyemail** is a Python library designed to simplify email communication. It provides straightforward interfaces for sending and receiving emails using IMAP and SMTP protocols.

## Features
- Easy-to-use interfaces for IMAP and SMTP connections.
- Retrieve, mark as read/unread, and delete emails.
- Send emails with attachments.
- Handle email parsing and metadata extraction seamlessly.


## Usage
### Basic Example
Here's a basic example to get you started with **pyemail**:

#### Receiving Emails
```python
from pyemail import IMAPConn, PyMsg

# Connect to the IMAP server
imap_conn = IMAPConn(user='your-email@example.com', pw='yourpassword', server='imap.example.com')

# Get the list of email IDs
email_ids = imap_conn.get_ids(unread_only=True)

# Fetch an email by ID
email_id = email_ids[0]
email_msg = PyMsg(id=email_id, con=imap_conn)

# Print email details
print(f"Subject: {email_msg.subject}")
print(f"From: {email_msg.sender}")
print(f"To: {email_msg.recipients}")
print(f"Date: {email_msg.date}")
print(f"Body: {email_msg.body}")

# Mark the email as read
email_msg.mark_read()
```

#### Sending Emails
```python
from pyemail import SMTPConn
from pathlib import Path

# Connect to the SMTP server
smtp_conn = SMTPConn(user='your-email@example.com', pw='yourpassword', server='smtp.example.com')

# Send an email
smtp_conn.send_email(
    recipients=['recipient@example.com'],
    cc=['cc@example.com'],
    subject='Test Email',
    body='This is a test email sent using pyemail.',
    filepath=Path('path/to/attachment.txt')
)
```

## API Reference
### `IMAPConn`
**IMAPConn** handles the connection to the IMAP server and provides methods to interact with emails.

#### Methods
- `login()`: Logs into the IMAP server.
- `logout()`: Logs out of the IMAP server.
- `get_ids(unread_only=False, read_only=False)`: Retrieves email IDs.
- `mark_read(email_id)`: Marks an email as read.
- `mark_unread(email_id)`: Marks an email as unread.
- `get_email(email_id)`: Fetches an email by ID.
- `idle(stopevent, idletag='A001', buffer_timeout=3, refresh_idle=0, logger=None)`: Sends an `IDLE` command to the IMAP server.

### `SMTPConn`
**SMTPConn** handles the connection to the SMTP server and provides methods to send emails.

#### Methods
- `login()`: Logs into the SMTP server.
- `quit()`: Logs out of the SMTP server.
- `send_email(recipients, cc=None, subject='', body='', filepath=None)`: Sends an email.

### `PyMsg`
**PyMsg** represents an email message and provides properties to access email details.

#### Properties
- `exists`: Checks if the email exists.
- `message`: Retrieves the raw email message.
- `date`: Retrieves the email's date.
- `recipients`: Retrieves the list of recipients.
- `sender`: Retrieves the sender's email address.
- `subject`: Retrieves the email subject.
- `body`: Retrieves the email body.

#### Methods
- `pull()`: Fetches email details from the server.
- `mark_read()`: Marks the email as read.
- `mark_unread()`: Marks the email as unread.
- `delete()`: Deletes the email.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
