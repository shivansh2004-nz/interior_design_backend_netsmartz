import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .settings import settings

def generate_otp():
    return str(random.randint(100000, 999999))

async def send_otp_email(email: str, otp: str):
    msg = MIMEMultipart()
    msg['From'] = settings.SMTP_USER
    msg['To'] = email
    msg['Subject'] = "Your Verification Code - Interior Design AI"

    body = f"""
    <h2>Welcome to Interior Design AI!</h2>
    <p>Your one-time verification code is:</p>
    <h1 style="color: #4f46e5; letter-spacing: 5px;">{otp}</h1>
    <p>This code will expire in 5 minutes.</p>
    """
    msg.attach(MIMEText(body, 'html'))

    try:
        # SMTP_SSL for port 465, starttls for 587
        if settings.SMTP_PORT == 587:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
            
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
