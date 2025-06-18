import random
from django.core.mail import send_mail
from django.conf import settings

def generate_otp():
    return str(random.randint(100000, 999999))

from django.core.mail import BadHeaderError

def send_otp_via_email(email, otp):
    subject = 'Your OneClickMart OTP Code'
    message = f'Your One-Time Password (OTP) is: {otp}\n\nUse this to complete your signup or verification.'
    email_from = settings.EMAIL_HOST_USER
    recipient_list = [email]

    try:
        send_mail(subject, message, email_from, recipient_list)
    except BadHeaderError:
        print("Invalid header found.")
    except Exception as e:
        print(f"An error occurred: {e}")
