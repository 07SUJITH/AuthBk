import logging

from decouple import config
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


class Util:
    @staticmethod
    def send_email(data):
        try:
            subject = data["subject"]
            from_email = config("EMAIL_HOST_USER")
            to_email = [data["to_email"]]
            html_content = data["body"]
            text_content = (
                "This is a plain-text version of the email. "
                "If you're seeing this, your email client does not support HTML."
            )

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=to_email,
                headers={
                    "Reply-To": from_email,
                    "Return-Path": from_email,
                    "X-Mailer": "Django App",
                    "X-Priority": "1",
                    "X-Importance": "High",
                },
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=False)
            return True

        except Exception:
            logger.exception("Error sending email:")
            return False
