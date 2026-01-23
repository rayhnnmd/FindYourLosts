from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import pymysql
import config
import os

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['role'] = user['role']
            return redirect('/dashboard')

        flash("Invalid email or password")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    keyword = request.args.get('keyword', '')
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    location = request.args.get('location', '')

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

    if location:
        query += " AND location LIKE %s"
        params.append(f"%{location}%")

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    html = f"""
    <h2>Welcome {session['user_name']}</h2>

    <form method="GET">
        <input type="text" name="keyword" placeholder="Search keyword" value="{keyword}">
        <input type="text" name="category" placeholder="Category" value="{category}">
        <input type="text" name="location" placeholder="Location" value="{location}">

        <select name="type">
            <option value="">All</option>
            <option value="lost" {'selected' if item_type=='lost' else ''}>Lost</option>
            <option value="found" {'selected' if item_type=='found' else ''}>Found</option>
        </select>

        <button type="submit">Search</button>
    </form>

    <br>
    <a href="/post-item">Post New Item</a> |
    <a href="/logout">Logout</a>
    <hr>
    """

    if not items:
        html += "<p>No items found.</p>"

    for item in items:
        html += f"""
        <div style="border:1px solid #ccc; padding:10px; margin-bottom:10px;">
            <h3>
              <a href="/item/{item['id']}">{item['title']}</a>
              ({item['type']}) — <b>{item['status']}</b>
            </h3>
            <p>{item['description'][:120]}...</p>
            <p><b>Category:</b> {item['category']}</p>
            <p><b>Location:</b> {item['location']}</p>
        """

        if item['image']:
            html += f"<img src='/static/uploads/{item['image']}' width='150'><br>"

        html += "</div>"

    return html

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

        image_filename = None
        file = request.files.get('image')

        if file and file.filename != '' and allowed_file(file.filename):
            image_filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO items
            (user_id, title, description, category, location, item_date, image, type)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            session['user_id'],
            title,
            description,
            category,
            location,
            item_date,
            image_filename,
            item_type
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

    html = f"""
    <h2>{item['title']} ({item['type']})</h2>
    <p>{item['description']}</p>
    <p><b>Category:</b> {item['category']}</p>
    <p><b>Location:</b> {item['location']}</p>
    <p><b>Date:</b> {item['item_date']}</p>
    <p><b>Status:</b> <b>{item['status'].upper()}</b></p>
    """

    if item['image']:
        html += f"<img src='/static/uploads/{item['image']}' width='300'><br><br>"

    if item['status'] == 'open':
        html += f"<a href='/claim/{item_id}'>Claim Item</a><br><br>"

    if item['status'] == 'claimed' and item['user_id'] == session['user_id']:
        html += f"<a href='/return/{item_id}'>Mark as Returned</a><br><br>"

    html += "<a href='/dashboard'>Back to Dashboard</a>"
    return html

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

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
