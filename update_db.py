import pymysql
import config

def update_db():
    conn = pymysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB
    )
    cursor = conn.cursor()
    try:
        # Check if column exists first
        cursor.execute("SHOW COLUMNS FROM items LIKE 'claimed_by'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE items ADD COLUMN claimed_by INT NULL")
        
        # Add delivery details columns
        cursor.execute("SHOW COLUMNS FROM items LIKE 'delivered_to_name'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE items ADD COLUMN delivered_to_name VARCHAR(100) NULL")
            
        cursor.execute("SHOW COLUMNS FROM items LIKE 'delivered_to_contact'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE items ADD COLUMN delivered_to_contact VARCHAR(100) NULL")

        # Add profile_pic column to users table
        cursor.execute("SHOW COLUMNS FROM users LIKE 'profile_pic'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT NULL")

        # Add profile defaults and settings
        cursor.execute("SHOW COLUMNS FROM users LIKE 'default_contact'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN default_contact VARCHAR(255) NULL")

        cursor.execute("SHOW COLUMNS FROM users LIKE 'contact_visibility'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN contact_visibility VARCHAR(20) DEFAULT 'public'")

        cursor.execute("SHOW COLUMNS FROM users LIKE 'email_notifications'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD COLUMN email_notifications TINYINT(1) DEFAULT 1")
        
        # Add settings table
        cursor.execute("SHOW TABLES LIKE 'settings'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_key VARCHAR(50) UNIQUE NOT NULL,
                    setting_value VARCHAR(255) NOT NULL
                )
            """)
            # Initialize default settings
            default_settings = [
                ('auto_approve_posts', '1'),
                ('maintenance_mode', '0'),
                ('max_upload_size_mb', '5'),
                ('broadcast_message', ''),
                ('email_notifications_enabled', '0')
            ]
            cursor.executemany("INSERT IGNORE INTO settings (setting_key, setting_value) VALUES (%s, %s)", default_settings)
        
        # Add claims table
        cursor.execute("SHOW TABLES LIKE 'claims'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE claims (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    item_id INT NOT NULL,
                    user_id INT NOT NULL,
                    proof TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
        
        # Ensure status column is set up
        cursor.execute("ALTER TABLE items MODIFY COLUMN status VARCHAR(20) DEFAULT 'open'")
        # New table: messages
        print("Validating 'messages' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL,
                sender_id INT NOT NULL,
                receiver_id INT NOT NULL,
                body TEXT NOT NULL,
                read_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        print("Database updated successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_db()
