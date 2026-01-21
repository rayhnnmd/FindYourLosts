from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash
import pymysql
import config
import MySQLdb.cursors

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

app.config['MYSQL_HOST'] = config.MYSQL_HOST
app.config['MYSQL_USER'] = config.MYSQL_USER
app.config['MYSQL_PASSWORD'] = config.MYSQL_PASSWORD
app.config['MYSQL_DB'] = config.MYSQL_DB

mysql = MYSQL(app)

@app.route('/')
def home():
    return redirect('/login')