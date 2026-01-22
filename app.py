from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import check_password_hash
import pymysql
import config

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

def get_db_connection():
    return pymysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )

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
    
    return f"""
    <h2>Welcome {session['user_name']}</h2>
    <p>Role: {session['role']}</p>
    <a href="/logout">logout</a>
    """

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)