import pymysql
import config
import os
from werkzeug.security import generate_password_hash

def create_admin():
    conn = pymysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    
    email = os.environ.get('ADMIN_EMAIL', 'admin@findyourlosts.com')
    password = os.environ.get('ADMIN_PASSWORD', 'rayhnn1221@#')
    hashed_pw = generate_password_hash(password)
    
    # Check if exists
    cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
    existing = cursor.fetchone()
    
    if existing:
        print("Updating existing admin user...")
        cursor.execute("UPDATE users SET password=%s, role='admin' WHERE email=%s", (hashed_pw, email))
    else:
        print("Creating new admin user...")
        cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                       ("Admin User", email, hashed_pw, 'admin'))
    
    conn.commit()
    conn.close()
    print("Admin user setup complete.")

if __name__ == "__main__":
    create_admin()
