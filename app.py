from flask import Flask, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import pymysql
import config
import os
import firebase_admin
from firebase_admin import credentials, auth

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
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

def admin_only():
    return 'user_id' in session and session.get('role') == 'admin'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

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
       
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        determined_role = 'admin' if email == 'rayhnmd024@gmail.com' else 'user'
        
        if user:
            if user['role'] != determined_role:
                cursor.execute("UPDATE users SET role = %s WHERE id = %s", (determined_role, user['id']))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE id = %s", (user['id'],))
                user = cursor.fetchone()

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
        else:
            from werkzeug.security import generate_password_hash
            import secrets
            
            dummy_password = generate_password_hash(secrets.token_hex(16))
            
            cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)", 
                           (name, email, dummy_password, determined_role))
            conn.commit()
            
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            new_user = cursor.fetchone()
            
            session['user_id'] = new_user['id']
            session['user_name'] = new_user['name']
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

    query = "SELECT * FROM items WHERE approved =1"
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

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    return render_template('dashboard.html', items=items, keyword=keyword, item_type=item_type, category=category, location=location)

@app.route('/my-posts')
def my_posts():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    items = cursor.fetchall()
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
            image_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        conn = get_db_connection()
        cursor = conn.cursor()
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
            0,
            contact_info
        ))
        conn.commit()
        conn.close()

        return redirect('/dashboard')

    return render_template('post_item.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = %s", (item_id,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        return "<h3>Item not found</h3>"

    return render_template('item_detail.html', item=item)

@app.route('/claim/<int:item_id>')
def claim_item(item_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE items SET status='claimed'
        WHERE id=%s AND status='open'
    """, (item_id,))
    conn.commit()
    conn.close()

    return redirect(f'/item/{item_id}')

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
    if not admin_only():
        return "Access Denied", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items ORDER BY created_at DESC")
    items = cursor.fetchall()
    conn.close()

    return render_template('admin.html', items=items)

@app.route('/admin/approve/<int:item_id>')
def approve_item(item_id):
    if not admin_only():
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
    if not admin_only():
        return "Access Denied", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT image FROM items WHERE id=%s", (item_id,))
    item = cursor.fetchone()

    if item and item['image']:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], item['image']))
        except:
            pass

    cursor.execute("DELETE FROM items WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()

    return redirect('/admin')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
