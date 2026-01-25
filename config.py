import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'zahara1221@#')
MYSQL_DB = os.environ.get('MYSQL_DB', 'findyourlosts')


SECRET_KEY = os.environ.get('SECRET_KEY', 'findyourlosts_secret_key')

UPLOAD_FOLDER = 'static/uploads'
