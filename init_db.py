import pymysql
import config
import os

def init_db():
    print("Connecting to database...")
    try:
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        # 1. Create Users Table
        print("Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                profile_pic TEXT NULL,
                default_contact VARCHAR(255) NULL,
                contact_visibility VARCHAR(20) DEFAULT 'public',
                email_notifications TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Create Items Table
        print("Creating items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(100) NOT NULL,
                location VARCHAR(255) NOT NULL,
                item_date DATE NOT NULL,
                image VARCHAR(255) NULL,
                type VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'open',
                approved TINYINT(1) DEFAULT 0,
                contact_info VARCHAR(255) NULL,
                claimed_by INT NULL,
                delivered_to_name VARCHAR(100) NULL,
                delivered_to_contact VARCHAR(100) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 3. Create Settings Table
        print("Creating settings table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(50) UNIQUE NOT NULL,
                setting_value VARCHAR(255) NOT NULL
            )
        """)
        
        # Seed default settings
        default_settings = [
            ('auto_approve_posts', '1'),
            ('maintenance_mode', '0'),
            ('max_upload_size_mb', '5'),
            ('broadcast_message', ''),
            ('email_notifications_enabled', '0')
        ]
        cursor.executemany("INSERT IGNORE INTO settings (setting_key, setting_value) VALUES (%s, %s)", default_settings)
        
        conn.commit()
        print("Database initialized successfully!")
        conn.close()
    except Exception as e:
        print(f"DATABASE INITIALIZATION ERROR: {e}")

if __name__ == "__main__":
    init_db()
