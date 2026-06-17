import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'kumbuflow_secret_2026_fixed'
app.permanent_session_lifetime = timedelta(days=7)

# 1. FUNÇÕES DE SUPORTE (DB, Logs, etc.)
def get_db_connection():
    # ... (o teu código de conexão continua igual)
    pass

def query_db(query, args=(), one=False):
    # ... (igual)
    pass

def execute_db(query, args=()):
    # ... (igual)
    pass

# 2. ROTAS (Login tem de ser a primeira rota lida)
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (o teu código de login completo)
    pass

@app.route('/')
def index():
    return redirect(url_for('login'))

# 3. O BEFORE_REQUEST (Agora colocado DEPOIS das rotas principais)
@app.before_request
def make_session_permanent():
    session.permanent = True

@app.before_request
def verificar_acesso():
    # Esta verificação garante que não entramos em loop infinito no login
    if request.endpoint in ['login', 'static']:
        return None
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

# 4. RESTANTE DAS ROTAS (Dashboard, Stock, Vendas...)
@app.route('/dashboard')
def dashboard():
    # ... (o teu código corrigido)
    pass

# ... (outras rotas)

if __name__ == '__main__':
    app.run(port=5050, debug=True)
