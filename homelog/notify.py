import os
import smtplib
import ssl

from email.message import EmailMessage

port = 465
smtp_server = "mail.gandi.net"


def send(subject, message=""):
    msg = EmailMessage()
    msg["From"] = "homelog@france.sh"
    msg["To"] = os.environ.get("MAIL_TO")
    msg["Subject"] = subject
    msg.set_content(message)

    login = os.environ.get("MAIL_LOGIN")
    password = os.environ.get("MAIL_PASSWORD")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(login, password)
        server.send_message(msg)
