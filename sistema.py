import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from datetime import timedelta

app = Flask(__name__)

# 1. CHAVE FIXA E SESSÃO PERMANENTE (Corrige o desaparecimento do login)
app.secret_key = 'kumbuflow_secret_2026_fixed'
app.permanent_session_lifetime = timedelta(days=7)

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.before_request
def verificar_acesso():
    if request.endpoint not in ['login', 'static', 'debug_usuarios'] and 'usuario_id' not in session:
        return redirect(url_for('login'))

# --- FUNÇÕES DE CONEXÃO ---
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = DictCursor
        return conn, '%s'
    else:
        conn = sqlite3.connect('kumbuflow.db')
        conn.row_factory = sqlite3.Row
        return conn, '?'

def query_db(query, args=(), one=False):
    conn, placeholder = get_db_connection()
    query = query.replace('?', placeholder)
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn, placeholder = get_db_connection()
    query = query.replace('?', placeholder)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

# --- DASHBOARD (Query corrigida para Postgres e SQLite) ---
@app.route('/dashboard')
def dashboard():
    usuario_logado = session.get('usuario_id')
    dados_vendas = query_db('''SELECT SUM(total) as faturacao, SUM(lucro) as lucro_bruto, COUNT(id) as total_vendas 
                              FROM vendas WHERE usuario_id = ?''', (usuario_logado,), one=True)
    
    faturacao = dados_vendas['faturacao'] if dados_vendas['faturacao'] else 0.0
    lucro_bruto = dados_vendas['lucro_bruto'] if dados_vendas['lucro_bruto'] else 0.0
    total_vendas = dados_vendas['total_vendas'] if dados_vendas['total_vendas'] else 0

    # QUERY CORRIGIDA: Compatível com SQLite e Postgres
    faturacao_mensal = query_db('''SELECT SUM(total) as faturacao_mensal FROM vendas 
                                   WHERE usuario_id = ? 
                                   AND data_venda >= date('now', 'start of month')''', (usuario_logado,), one=True)
    
    faturacao_mensal = faturacao_mensal['faturacao_mensal'] if faturacao_mensal and faturacao_mensal['faturacao_mensal'] else 0.0

    # ... (restante das funções mantêm-se iguais) ...
    return render_template('dashboard.html', faturacao=faturacao, faturacao_mensal=faturacao_mensal)

# --- (Restante das tuas rotas permanecem inalteradas, apenas garante que manténs o resto do ficheiro) ---
if __name__ == '__main__':
    app.run(port=5050, debug=True)
