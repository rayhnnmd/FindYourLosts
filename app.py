from flask import Flask, render_template, request, redirect, session, flash, jsonify, Response
import csv
import io
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import pymysql
import config
import os
import uuid
import firebase_admin
from firebase_admin import credentials, auth
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading

from whitenoise import WhiteNoise

app = Flask(__name__)
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/', prefix='static/')
app.secret_key = config.SECRET_KEY

def send_broadcast_emails(item_title, item_type, item_location):
    def send_thread():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Fetch all users who want notifications
            cursor.execute("SELECT email FROM users WHERE email_notifications = 1")
            users = cursor.fetchall()
            conn.close()

            if not users:
                return

            # SMTP Setup
            server = smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT)
            if config.MAIL_USE_TLS:
                server.starttls()
            server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)

            for user in users:
                msg = MIMEMultipart()
                msg['From'] = config.MAIL_DEFAULT_SENDER[0] + f" <{config.MAIL_DEFAULT_SENDER[1]}>"
                msg['To'] = user['email']
                msg['Subject'] = f"New {item_type.capitalize()} Item: {item_title}"

                body = f"""
                Hello,

                A new {item_type} item has been posted on FindYourLosts!

                Item: {item_title}
                Location: {item_location}

                Check it out here: http://127.0.0.1:5000/dashboard

                Stay safe,
                The FindYourLosts Team
                """
                msg.attach(MIMEText(body, 'plain'))
                server.send_message(msg)

            server.quit()
        except Exception as e:
            print(f"Error sending broadcast emails: {e}")

    threading.Thread(target=send_thread).start()

UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    if firebase_creds_json:
        # Initialize from environment variable
        creds_dict = json.loads(firebase_creds_json)
        cred = credentials.Certificate(creds_dict)
        firebase_admin.initialize_app(cred)
    else:
        # Fallback to local file
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Warning: Firebase Admin SDK not initialized. {e}")


def get_db_connection():
    return pymysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def staff_only():
    return 'user_id' in session and session.get('role') in ['admin', 'moderator']

def admin_only():
    return 'user_id' in session and session.get('role') == 'admin'

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = %s", (key,))
    result = cursor.fetchone()
    conn.close()
    return result['setting_value'] if result else default

def get_int_setting(key, default=0):
    val = get_setting(key)
    if val == 'on' or val == '1':
        return 1
    try:
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default

@app.before_request
def check_maintenance_mode():
    # Only check for non-admin/staff users
    if not staff_only():
        # List of allowed endpoints during maintenance
        allowed_endpoints = ['login', 'logout', 'google_login', 'home', 'static']
        if request.endpoint in allowed_endpoints:
            return
            
        if get_int_setting('maintenance_mode') == 1:
            return render_template('maintenance.html'), 503

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.context_processor
def inject_notifications():
    if 'user_id' not in session:
        return {'notifications': [], 'broadcast_message': ''}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get broadcast message
    cursor.execute("SELECT setting_value FROM settings WHERE setting_key = 'broadcast_message'")
    broadcast = cursor.fetchone()
    broadcast_text = broadcast['setting_value'] if broadcast else ""
    
    # Get latest 5 items for notifications
    cursor.execute("SELECT id, title, type, created_at FROM items WHERE approved = 1 ORDER BY created_at DESC LIMIT 5")
    latest_items = cursor.fetchall()
    
    conn.close()
    
    return {
        'notifications': latest_items,
        'broadcast_message': broadcast_text
    }

@app.route('/login/google', methods=['POST'])
def google_login():
    data = request.json
    id_token = data.get('token')

    if not id_token:
        return jsonify({'success': False, 'error': 'No token provided'}), 400

    try:
        decoded_token = auth.verify_id_token(id_token, clock_skew_seconds=10)
        email = decoded_token['email']
        name = decoded_token.get('name', '')
        picture = decoded_token.get('picture', '')
       
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        determined_role = 'admin' if email == 'rayhnmd024@gmail.com' else 'user'
        if user:
            if user['role'] != determined_role or user.get('profile_pic') != picture:
                cursor.execute("UPDATE users SET role = %s, profile_pic = %s WHERE id = %s", (determined_role, picture, user['id']))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE id = %s", (user['id'],))
                user = cursor.fetchone()

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['user_pic'] = user.get('profile_pic', '')
            session['role'] = user['role']
        else:
            from werkzeug.security import generate_password_hash
            import secrets
            
            dummy_password = generate_password_hash(secrets.token_hex(16))
            
            cursor.execute("INSERT INTO users (name, email, password, role, profile_pic) VALUES (%s, %s, %s, %s, %s)", 
                           (name, email, dummy_password, determined_role, picture))
            conn.commit()
            
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            new_user = cursor.fetchone()
            
            session['user_id'] = new_user['id']
            session['user_name'] = new_user['name']
            session['user_email'] = new_user['email']
            session['user_pic'] = new_user.get('profile_pic', '')
            session['role'] = new_user['role']

        conn.close()
        
        return jsonify({'success': True})

    except Exception as e:
        print(f"Error validating token: {e}")
        return jsonify({'success': False, 'error': str(e)}), 401

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    keyword = request.args.get('keyword', '')
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    location = request.args.get('location', '')
    recent = request.args.get('recent', '')

    query = "SELECT * FROM items WHERE approved = 1"
    params = []

    if keyword:
        query += " AND (title LIKE %s OR description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if item_type:
        query += " AND type = %s"
        params.append(item_type)

    if category:
        query += " AND category LIKE %s"
        params.append(f"%{category}%")

    if location:
        query += " AND location LIKE %s"
        params.append(f"%{location}%")

    if recent == '1':
        query += " AND created_at >= NOW() - INTERVAL 1 DAY"

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    return render_template('dashboard.html', items=items, keyword=keyword, item_type=item_type, category=category, location=location, recent=recent)

@app.route('/my-posts')
def my_posts():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    items = cursor.fetchall()
    
    # Get pending claims count for each item
    for item in items:
        cursor.execute("SELECT COUNT(*) as count FROM claims WHERE item_id = %s AND status = 'pending'", (item['id'],))
        item['pending_claims'] = cursor.fetchone()['count']
        
    conn.close()

    return render_template('my_posts.html', items=items)

@app.route('/post-item', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['location']
        item_date = request.form['item_date']
        item_type = request.form['type']
        contact_info = request.form['contact_info']

        image_filename = None
        file = request.files.get('image')

        if file and file.filename != '' and allowed_file(file.filename):
            # Generate a unique filename to prevent collisions
            ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        conn = get_db_connection()
        cursor = conn.cursor()
        approved = get_int_setting('auto_approve_posts', 1)
        cursor.execute("""
            INSERT INTO items
            (user_id, title, description, category, location, item_date, image, type, approved, contact_info)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session['user_id'],
            title,
            description,
            category,
            location,
            item_date,
            image_filename,
            item_type,
            approved,
            contact_info
        ))
        conn.commit()
        conn.close()

        # Trigger email broadcast if enabled
        if get_int_setting('email_notifications_enabled', 0) == 1:
            send_broadcast_emails(title, item_type, location)

        return redirect('/dashboard')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT default_contact FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()

    return render_template('post_item.html', default_contact=user['default_contact'] if user else '')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()

    # Get recent items (last 24 hours), excluding current item, limit 4
    cursor.execute("""
        SELECT * FROM items 
        WHERE approved = 1 
        AND id != %s 
        AND created_at >= NOW() - INTERVAL 24 HOUR 
        ORDER BY created_at DESC 
        LIMIT 4
    """, (item_id,))
    recent_items = cursor.fetchall()

    messagers = []
    if 'user_id' in session and item and session['user_id'] == item['user_id']:
        cursor.execute("""
            SELECT DISTINCT u.id, u.name 
            FROM messages m
            JOIN users u ON (m.sender_id = u.id OR m.receiver_id = u.id)
            WHERE m.item_id = %s AND u.id != %s
        """, (item_id, session['user_id']))
        messagers = cursor.fetchall()

    conn.close()

    if not item:
        return "<h3>Item not found</h3>"

    return render_template('item_detail.html', item=item, recent_items=recent_items, messagers=messagers)

@app.route('/edit-item/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()

    # Ensure item exists and user is authorized
    if not item or item['user_id'] != session['user_id']:
        conn.close()
        flash("Unauthorized to edit this item.", "error")
        return redirect('/dashboard')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['location']
        item_date = request.form['item_date']
        item_type = request.form['type']
        contact_info = request.form['contact_info']

        file = request.files.get('image')
        if file and file.filename != '' and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            image_filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            
            cursor.execute("""
                UPDATE items 
                SET title=%s, description=%s, category=%s, location=%s, item_date=%s, type=%s, contact_info=%s, image=%s 
                WHERE id=%s AND user_id=%s
            """, (title, description, category, location, item_date, item_type, contact_info, image_filename, item_id, session['user_id']))
        else:
            cursor.execute("""
                UPDATE items 
                SET title=%s, description=%s, category=%s, location=%s, item_date=%s, type=%s, contact_info=%s
                WHERE id=%s AND user_id=%s
            """, (title, description, category, location, item_date, item_type, contact_info, item_id, session['user_id']))
        
        conn.commit()
        conn.close()
        flash("Item updated successfully!", "success")
        return redirect(f'/item/{item_id}')

    conn.close()
    return render_template('edit_item.html', item=item)

@app.route('/claim/<int:item_id>', methods=['GET', 'POST'])
def claim_item(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'GET':
        return redirect(f'/item/{item_id}')

    proof = request.form.get('proof')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if a pending claim already exists from this user
    cursor.execute("SELECT id FROM claims WHERE item_id = %s AND user_id = %s AND status = 'pending'", (item_id, session['user_id']))
    if cursor.fetchone():
        flash("You already have a pending claim for this item.", "warning")
        conn.close()
        return redirect(f'/item/{item_id}')
    
    # Insert new claim
    cursor.execute("""
        INSERT INTO claims (item_id, user_id, proof, status)
        VALUES (%s, %s, %s, 'pending')
    """, (item_id, session['user_id'], proof))
    
    conn.commit()
    conn.close()
    
    flash("Claim submitted successfully. Awaiting poster's review.", "success")
    return redirect(f'/item/{item_id}')

@app.route('/review-claims/<int:item_id>')
def review_claims(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM items WHERE id = %s AND user_id = %s", (item_id, session['user_id']))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return "Unauthorized or Not Found", 403
        
    cursor.execute("""
        SELECT c.*, u.name as user_name, u.email as user_email 
        FROM claims c JOIN users u ON c.user_id = u.id 
        WHERE c.item_id = %s AND c.status = 'pending'
    """, (item_id,))
    claims = cursor.fetchall()
    conn.close()
    
    return render_template('review_claims.html', item=item, claims=claims)

@app.route('/handle-claim/<int:claim_id>/<action>', methods=['POST'])
def handle_claim(claim_id, action):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, i.user_id as owner_id 
        FROM claims c JOIN items i ON c.item_id = i.id 
        WHERE c.id = %s
    """, (claim_id,))
    claim_info = cursor.fetchone()

    if not claim_info or claim_info['owner_id'] != session['user_id']:
        conn.close()
        return "Unauthorized", 403

    if action == 'approve':
        cursor.execute("UPDATE claims SET status='approved' WHERE id=%s", (claim_id,))
        cursor.execute("UPDATE claims SET status='rejected' WHERE item_id=%s AND id!=%s", (claim_info['item_id'], claim_id))
        cursor.execute("UPDATE items SET status='claimed', claimed_by=%s WHERE id=%s", (claim_info['user_id'], claim_info['item_id']))
        flash("Claim approved successfully.", "success")
    elif action == 'reject':
        cursor.execute("UPDATE claims SET status='rejected' WHERE id=%s", (claim_id,))
        flash("Claim rejected.", "success")

    conn.commit()
    conn.close()

    return redirect(f"/review-claims/{claim_info['item_id']}")

@app.route('/claimed-items')
def claimed_items():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    # Show items user claimed AND items they successfully delivered
    cursor.execute("""
        SELECT * FROM items 
        WHERE claimed_by = %s OR (user_id = %s AND status = 'delivered') 
        ORDER BY created_at DESC
    """, (session['user_id'], session['user_id']))
    items = cursor.fetchall()
    conn.close()

    return render_template('claimed_items.html', items=items)

@app.route('/return/<int:item_id>')
def return_item(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE items SET status='returned'
        WHERE id=%s AND user_id=%s
    """, (item_id, session['user_id']))
    conn.commit()
    conn.close()

    return redirect(f'/item/{item_id}')


@app.route('/admin')
def admin_dashboard():
    if not staff_only():
        return "Access Denied", 403
        
    keyword = request.args.get('keyword', '')
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')

    query = "SELECT * FROM items WHERE 1=1"
    params = []

    if keyword:
        query += " AND (title LIKE %s OR description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if item_type:
        query += " AND type = %s"
        params.append(item_type)

    if category:
        query += " AND category LIKE %s"
        params.append(f"%{category}%")

    if status:
        if status == 'approved':
            query += " AND approved = 1"
        elif status == 'pending':
            query += " AND approved = 0"

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    return render_template('admin.html', items=items, 
                           keyword=keyword, 
                           item_type=item_type, 
                           category=category, 
                           status=status)

@app.route('/admin/export')
def export_items_csv():
    if not staff_only():
        return "Access Denied", 403

    keyword = request.args.get('keyword', '')
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')

    query = "SELECT * FROM items WHERE 1=1"
    params = []

    if keyword:
        query += " AND (title LIKE %s OR description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    if item_type:
        query += " AND type = %s"
        params.append(item_type)
    if category:
        query += " AND category LIKE %s"
        params.append(f"%{category}%")
    if status:
        if status == 'approved':
            query += " AND approved = 1"
        elif status == 'pending':
            query += " AND approved = 0"

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    if items:
        writer.writerow(items[0].keys())
        for item in items:
            writer.writerow(item.values())

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=exported_items.csv"}
    )

@app.route('/admin/approve/<int:item_id>')
def approve_item(item_id):
    if not staff_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE items SET approved = 1 WHERE id = %s
    """,(item_id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

@app.route('/admin/delete/<int:item_id>')
def delete_item(item_id):
    if not staff_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT image FROM items WHERE id=%s", (item_id,))
    item = cursor.fetchone()

    if item and item['image']:
        # Safety check: Only delete file if no other items are using it
        cursor.execute("SELECT COUNT(*) as count FROM items WHERE image = %s AND id != %s", (item['image'], item_id))
        usage_count = cursor.fetchone()['count']
        
        if usage_count == 0:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image']))
            except:
                pass

    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()

    return redirect('/admin')


@app.route('/delete-item/<int:item_id>')
def delete_user_item(item_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the item belongs to the user
    cursor.execute("SELECT image, user_id FROM items WHERE id=%s", (item_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return "Item not found", 404

    if item['user_id'] != session['user_id']:
        conn.close()
        return "Unauthorized", 403

    # Delete image if exists and not shared
    if item['image']:
        # Safety check: Only delete file if no other items are using it
        cursor.execute("SELECT COUNT(*) as count FROM items WHERE image = %s AND id != %s", (item['image'], item_id))
        usage_count = cursor.fetchone()['count']

        if usage_count == 0:
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image']))
            except:
                pass

    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()

    return redirect('/my-posts')


@app.route('/mark-delivered/<int:item_id>', methods=['POST'])
def mark_delivered(item_id):
    if 'user_id' not in session:
        return redirect('/login')
    
    name = request.form.get('delivered_to_name')
    contact = request.form.get('delivered_to_contact')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    
    if not item or item['user_id'] != session['user_id']:
        conn.close()
        return "Unauthorized", 403
        
    cursor.execute("""
        UPDATE items 
        SET status = 'delivered', 
            delivered_to_name = %s, 
            delivered_to_contact = %s 
        WHERE id = %s
    """, (name, contact, item_id))
    
    conn.commit()
    conn.close()
    
    return redirect('/my-posts')


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user stats
    cursor.execute("SELECT COUNT(*) as posts_count FROM items WHERE user_id = %s", (session['user_id'],))
    posts_count = cursor.fetchone()['posts_count']
    
    cursor.execute("SELECT COUNT(*) as claims_count FROM items WHERE claimed_by = %s", (session['user_id'],))
    claims_count = cursor.fetchone()['claims_count']
    
    conn.close()
    
    return render_template('profile.html', posts_count=posts_count, claims_count=claims_count)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        default_contact = request.form.get('default_contact')
        contact_visibility = request.form.get('contact_visibility')
        email_notifications = 1 if request.form.get('email_notifications') else 0
        
        cursor.execute("""
            UPDATE users 
            SET default_contact = %s, contact_visibility = %s, email_notifications = %s 
            WHERE id = %s
        """, (default_contact, contact_visibility, email_notifications, session['user_id']))
        conn.commit()
        conn.close()
        return redirect('/settings')

    cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template('settings.html', user=user)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not staff_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        # List of keys that come from checkboxes
        checkbox_keys = ['auto_approve_posts', 'maintenance_mode', 'email_notifications_enabled']
        
        for key, value in request.form.items():
            # If it's a checkbox and it's 'on', save as '1'
            if key in checkbox_keys and value == 'on':
                value = '1'
            cursor.execute("UPDATE settings SET setting_value = %s WHERE setting_key = %s", (value, key))
            
        # Handle unchecked checkboxes (they don't appear in request.form)
        for key in checkbox_keys:
            if key not in request.form:
                cursor.execute("UPDATE settings SET setting_value = '0' WHERE setting_key = %s", (key,))
            
        conn.commit()
        flash("Settings updated successfully!", "success")
        return redirect('/admin/settings')

    cursor.execute("SELECT * FROM settings")
    settings_rows = cursor.fetchall()
    settings_dict = {row['setting_key']: row['setting_value'] for row in settings_rows}
    conn.close()
    
    return render_template('admin_settings.html', settings=settings_dict)

@app.route('/admin/users')
def admin_users():
    if not staff_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, profile_pic FROM users ORDER BY role DESC, name ASC")
    users = cursor.fetchall()
    conn.close()
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/assign-moderator', methods=['POST'])
def assign_moderator():
    if not staff_only():
        return "Access Denied", 403
    
    email = request.form.get('email')
    if not email:
        flash("Email is required", "error")
        return redirect('/admin/users')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'moderator' WHERE email = %s AND role = 'user'", (email,))
    if cursor.rowcount > 0:
        conn.commit()
        flash(f"Successfully promoted {email} to Moderator!", "success")
    else:
        flash(f"User with email {email} not found or is already a staff member.", "error")
    conn.close()
    
    return redirect('/admin/users')

@app.route('/admin/delivery-history')
def admin_delivered():
    print("DEBUG: Hitting admin_delivered route")
    if not staff_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch items that are delivered
    cursor.execute("""
        SELECT i.*, u.name as claimant_name, u.email as claimant_email 
        FROM items i 
        LEFT JOIN users u ON i.claimed_by = u.id 
        WHERE i.status = 'delivered'
        ORDER BY i.created_at DESC
    """)
    items = cursor.fetchall()
    conn.close()
    
    return render_template('admin_delivered.html', items=items)

# --- Messaging Routes ---

@app.route('/messages/<int:item_id>/<int:other_user_id>')
def messages_view(item_id, other_user_id):
    if 'user_id' not in session:
        return redirect('/login')
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get item
    cursor.execute("SELECT id, title, user_id FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        flash("Item not found.", "error")
        return redirect('/')
        
    # Security: exactly one of the participants must be the item owner
    print(f"DEBUG messages_view: item_user_id={item['user_id']}, session_user_id={session.get('user_id')}, other_user_id={other_user_id}")
    if int(item['user_id']) not in [int(session['user_id']), int(other_user_id)]:
        conn.close()
        flash("Not authorized to view these messages.", "error")
        return redirect('/')
        
    # Get other user details
    cursor.execute("SELECT id, name FROM users WHERE id = %s", (other_user_id,))
    other_user = cursor.fetchone()
    
    conn.close()
    
    if not other_user:
        flash("User not found.", "error")
        return redirect('/')
        
    return render_template('chat.html', item=item, other_user=other_user)

@app.route('/api/messages/<int:item_id>/<int:other_user_id>', methods=['GET', 'POST'])
def api_messages(item_id, other_user_id):
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    current_user_id = session['user_id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Validate authorization (either current user is item owner, or current user is the participant)
    cursor.execute("SELECT user_id FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    
    if not item:
        conn.close()
        return jsonify({"error": "Item not found"}), 404
        
    if int(item['user_id']) not in [int(current_user_id), int(other_user_id)]:
        conn.close()
        return jsonify({"error": "Forbidden"}), 403

    if request.method == 'GET':
        # Fetch conversation between current_user and other_user for this item
        cursor.execute("""
            SELECT id, sender_id, receiver_id, body, created_at 
            FROM messages 
            WHERE item_id = %s 
              AND ((sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s))
            ORDER BY created_at ASC
        """, (item_id, current_user_id, other_user_id, other_user_id, current_user_id))
        messages = cursor.fetchall()
        
        # Mark as read (optional polish)
        # cursor.execute("UPDATE messages SET read_at = CURRENT_TIMESTAMP WHERE item_id = %s AND receiver_id = %s AND sender_id = %s AND read_at IS NULL", (item_id, current_user_id, other_user_id))
        # conn.commit()
        
        conn.close()
        
        # Format created_at for JSON serialization
        for msg in messages:
            if msg['created_at']:
                msg['created_at'] = msg['created_at'].isoformat()
                
        return jsonify(messages)

    if request.method == 'POST':
        body = request.form.get('body')
        if not body:
            conn.close()
            return jsonify({"error": "Message body is required"}), 400
            
        cursor.execute("""
            INSERT INTO messages (item_id, sender_id, receiver_id, body)
            VALUES (%s, %s, %s, %s)
        """, (item_id, current_user_id, other_user_id, body))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
