import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'zahara1221@#')
MYSQL_DB = os.environ.get('MYSQL_DB', 'findyourlosts')

SECRET_KEY = os.environ.get('SECRET_KEY', 'findyourlosts_secret_key')

UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'static/uploads')

# Email Configuration (SMTP)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your-app-password')
MAIL_DEFAULT_SENDER = (
    os.environ.get('MAIL_SENDER_NAME', 'FindYourLosts'),
    os.environ.get('MAIL_SENDER_EMAIL', 'your-email@gmail.com')
)
