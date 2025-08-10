import os, smtplib, ssl
from email.message import EmailMessage
from datetime import datetime, time, timedelta, date
import pgeocode

WORK_START = time(8, 15)
WORK_END = time(14, 0)
LAUNCH_DATE = date(2025, 8, 18)

def parse_hhmm(s: str):
    h, m = s.split(':')
    return time(int(h), int(m))

def within_hours(start_t, duration_min):
    # Calculate end time and verify it doesn’t exceed WORK_END
    dt_start = datetime.combine(datetime.today().date(), start_t)
    dt_end = dt_start + timedelta(minutes=duration_min)
    return dt_end.time() <= WORK_END, dt_end.time()

def is_weekday(d: date):
    return d.weekday() < 5  # 0=Mon..4=Fri

def after_launch(d: date):
    return d >= LAUNCH_DATE

def km_distance(postcode_a: str, postcode_b: str) -> float:
    nomi = pgeocode.Nominatim('gb')
    a = nomi.query_postal_code(postcode_a)
    b = nomi.query_postal_code(postcode_b)
    if a.isnull().any() or b.isnull().any():
        return 9999.0
    return float(pgeocode.GeoDistance('gb').query_postal_code(postcode_a, postcode_b))

def send_email(subject: str, body: str, to_addrs: list[str]):
    host = os.getenv('SMTP_HOST')
    port = int(os.getenv('SMTP_PORT', '587'))
    user = os.getenv('SMTP_USER')
    pwd = os.getenv('SMTP_PASS')
    sender = os.getenv('EMAIL_FROM', user)
    if not host or not user or not pwd:
        return False, 'SMTP not configured'
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(to_addrs)
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.send_message(msg)
    return True, 'sent'
