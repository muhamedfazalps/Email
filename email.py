import smtplib
import time
import os
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_validator import validate_email, EmailNotValidError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 📌 Your Email Credentials
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# 📌 File Paths
EMAIL_CSV_FILE = "jobseekers_email.csv"
SENT_EMAILS_FILE = "sent_emails_fyers.txt"
DAILY_COUNT_FILE = "daily_count_fyers.txt"

# 📌 Constants
EMAILS_PER_BATCH = 1
BATCH_DELAY_SECONDS = 10
DAILY_EMAIL_LIMIT = 400
RETRY_DELAY_SECONDS = 60  # Retry delay if sending fails
WAIT_24_HOURS_SECONDS = 86400  # Wait 24 hours if limit is reached

# ✅ Load & Validate Emails from CSV
def load_valid_emails():
    """Load valid emails from the CSV file and exclude already sent ones."""
    valid_emails = []
    
    if not os.path.exists(EMAIL_CSV_FILE):
        print(f"❌ Email CSV file '{EMAIL_CSV_FILE}' not found.")
        return []

    # Load already sent emails
    sent_emails = set()
    if os.path.exists(SENT_EMAILS_FILE):
        with open(SENT_EMAILS_FILE, "r", encoding="utf-8") as file:
            sent_emails = {line.strip() for line in file}

    # Read CSV and validate emails
    with open(EMAIL_CSV_FILE, "r", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if not row or not row[0].strip():
                continue  # Skip empty rows

            email = row[0].strip()
            if email in sent_emails:  # Skip already sent emails
                continue
            if validate_email_safely(email):
                valid_emails.append(email)
            else:
                print(f"⚠️ Skipping invalid email: {email}")

    return valid_emails


# ✅ Validate Emails Safely
def validate_email_safely(email):
    """Check if an email is valid."""
    try:
        v = validate_email(email, check_deliverability=True)
        return v["email"]
    except EmailNotValidError:
        return None

# ✅ Check if Email Was Sent Before
def has_email_been_sent(email):
    if not os.path.exists(SENT_EMAILS_FILE):
        return False
    with open(SENT_EMAILS_FILE, "r", encoding="utf-8") as file:
        return email in {line.strip() for line in file}

# ✅ Log Sent Emails
def log_sent_email(email):
    with open(SENT_EMAILS_FILE, "a", encoding="utf-8") as file:
        file.write(email + "\n")

# ✅ Send Email Function
def send_email(recipient_email):
    """Send an email to the recipient."""
    print(f"📤 Attempting to send email to: {recipient_email}")

    if has_email_been_sent(recipient_email):
        print(f"⚠️ Email already sent to: {recipient_email}")
        return False

    # 📧 Email Content
    subject = "You are shortlisted..."
    body = """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; color: #333; }
        .container { max-width: 600px; padding: 20px; border-radius: 10px; background: #f9f9f9; }
        h2 { color: #0066cc; }
        .btn { display: inline-block; padding: 10px 15px; color: #fff; background: #007bff; 
               text-decoration: none; border-radius: 5px; font-weight: bold; }
        .footer { font-size: 12px; color: #777; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🤖 JobFinder Bot</h2>
        <p>🚀 Get real-time job alerts, career tips, and hiring updates—all in one place for both freshers and experienced professionals.</p>
        <h3>✨ Why Join?</h3>
        <ul>
            <li>✅ No Ads – Enjoy pure job listings without distractions.</li>
            <li>✅ Direct Links – Apply instantly with no redirections.</li>
            <li>✅ Work From Home – Easily find remote opportunities.</li>
            <li>✅ Instant Alerts – Stay ahead with real-time updates.</li>
            <li>✅ Absolutely Free – Get all these benefits at no cost!</li>
        </ul>
        <p>🔔 <strong>Never miss an opportunity!</strong></p>
        <p><a href="https://t.me/+-edEYkC7C7gwODdl" class="btn">📲 Join Now</a></p>
        <p class="footer">💼 Spread success—share it!</p>
    </div>
</body>
</html>
"""

    # 🔥 FIX: Move this line above `msg.attach(...)`
    msg = MIMEMultipart()
    
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html", "utf-8"))  # Use UTF-8 encoding

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
        server.quit()

        print(f"✅ Email sent ")
        log_sent_email(recipient_email)
        increment_daily_count()
        return True

    except Exception as e:
        print(f"❌ Failed to send email to {recipient_email}: {e}")
        return False


# ✅ Track Daily Email Count
def increment_daily_count():
    today = datetime.now().date()
    count = 0

    if os.path.exists(DAILY_COUNT_FILE):
        with open(DAILY_COUNT_FILE, "r", encoding="utf-8") as file:
            date_str, count_str = file.readline().strip().split(",")
            last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            count = int(count_str) if last_date == today else 0

    count += 1
    with open(DAILY_COUNT_FILE, "w", encoding="utf-8") as file:
        file.write(f"{today},{count}")

    return count

# ✅ Get Current Daily Count
def get_daily_count():
    today = datetime.now().date()
    if os.path.exists(DAILY_COUNT_FILE):
        with open(DAILY_COUNT_FILE, "r", encoding="utf-8") as file:
            date_str, count_str = file.readline().strip().split(",")
            last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if last_date == today:
                return int(count_str)
    return 0

# ✅ Bulk Email Sender
def bulk_send_emails():
    emails = load_valid_emails()
    if not emails:
        print("🚫 No valid emails found.")
        return

    while True:
        daily_count = get_daily_count()
        if daily_count >= DAILY_EMAIL_LIMIT:
            print("⏳ Daily limit reached. Waiting 24 hours...")
            time.sleep(WAIT_24_HOURS_SECONDS)
            continue

        with ThreadPoolExecutor(max_workers=EMAILS_PER_BATCH) as executor:
            futures = []
            for email in emails[daily_count : daily_count + EMAILS_PER_BATCH]:
                futures.append(executor.submit(send_email, email))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ Error occurred: {e}. Retrying after delay...")
                    time.sleep(RETRY_DELAY_SECONDS)

        time.sleep(BATCH_DELAY_SECONDS)

# 🚀 Run the Program
if __name__ == "__main__":
    print("🚀 Starting bulk email sender...")
    bulk_send_emails()
