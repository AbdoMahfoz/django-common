from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as b64Error
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Model
from django.template.loader import render_to_string
from django.urls import get_resolver
from django.utils import timezone
from django.apps import apps
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
from threading import Thread

from .errors import InvalidUserModel, EmailTemplateNotFound, NotAllFieldCompiled


def sendConfirm(user, **kwargs):
    uses_custom_model = not(validateAndGetField('EMAIL_USER_MODEL', raise_error=False) is None)
    if uses_custom_model:
        user_fk = validateAndGetField('EMAIL_USER_MODEL_FK')
    active_field = validateAndGetField('EMAIL_ACTIVE_FIELD')
    try:
        setattr(user, active_field, False)
        user.save()
        if uses_custom_model:
            user = getattr(user, user_fk)
        try:
            token = kwargs['token']
        except KeyError:
            token = default_token_generator.make_token(user)

        email = urlsafe_b64encode(str(user.email).encode('utf-8'))
        t = Thread(target=sendConfirm_thread, args=(user.email, f'{email.decode("utf-8")}/{token}'))
        t.start()
    except AttributeError:
        raise InvalidUserModel('The user model you provided is invalid')


def sendConfirm_thread(email, token):
    email_server = validateAndGetField('EMAIL_SERVER')
    sender = validateAndGetField('EMAIL_FROM_ADDRESS')
    domain = validateAndGetField('EMAIL_PAGE_DOMAIN')
    subject = validateAndGetField('EMAIL_MAIL_SUBJECT')
    address = validateAndGetField('EMAIL_ADDRESS')
    port = validateAndGetField('EMAIL_PORT', default_type=int)
    password = validateAndGetField('EMAIL_PASSWORD')
    mail_plain = validateAndGetField('EMAIL_MAIL_PLAIN', raise_error=False)
    mail_html = validateAndGetField('EMAIL_MAIL_HTML', raise_error=False)

    if not (mail_plain or mail_html):  # Validation for mail_plain and mail_html as both of them have raise_error=False
        raise NotAllFieldCompiled(f"Both EMAIL_MAIL_PLAIN and EMAIL_MAIL_HTML missing from settings.py, at least one of them is required.")

    domain += '/' if not domain.endswith('/') else ''

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = email

    from .views import verify
    link = ''
    for k, v in get_resolver(None).reverse_dict.items():
        if k is verify and v[0][0][1][0]:
            addr = str(v[0][0][0])
            link = domain + addr[0: addr.index('%')] + token

    if mail_plain:
        try:
            text = render_to_string(mail_plain, {'link': link})
            part1 = MIMEText(text, 'plain')
            msg.attach(part1)
        except AttributeError:
            pass
        
    if mail_html:
        try:
            html = render_to_string(mail_html, {'link': link})
            part2 = MIMEText(html, 'html')
            msg.attach(part2)
        except AttributeError:
            pass

    if not msg.get_payload():
        raise EmailTemplateNotFound('No email template found')

    server = SMTP(email_server, port)
    server.starttls()
    server.login(address, password)
    server.sendmail(sender, email, msg.as_string())
    server.quit()


def validateAndGetField(field, raise_error=True, default_type=str):
    try:
        d = getattr(settings, field)
        if d == "" or d is None or not isinstance(d, default_type):
            raise AttributeError
        return d
    except AttributeError:
        if raise_error:
            raise NotAllFieldCompiled(f"Field {field} missing or invalid")
        return None


def verifyToken(email, email_token):
    try:
        try:
            user_fk = validateAndGetField("EMAIL_USER_MODEL_FK")
            args = {f"{user_fk}__email": urlsafe_b64decode(email).decode("utf-8")}
            users = apps.get_model(*validateAndGetField('EMAIL_USER_MODEL').split('.', 1)).objects.filter(**args)
            custom_user = True
        except NotAllFieldCompiled:
            users = get_user_model().objects.filter(email=urlsafe_b64decode(email).decode("utf-8"))
            custom_user = False
        for user in users:
            if custom_user:
                actual_user = getattr(user, user_fk)
            else:
                actual_user = user
            valid = default_token_generator.check_token(actual_user, email_token)
            if valid:
                active_field = validateAndGetField('EMAIL_ACTIVE_FIELD')
                setattr(user, active_field, True)
                actual_user.last_login = timezone.now()
                actual_user.save()
                if custom_user:
                    user.save()
                return valid
    except b64Error:
        pass
    return False