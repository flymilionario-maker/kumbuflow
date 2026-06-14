import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

app = Flask(__name__)
app.secret_key = 'kumbuflow_secret'

# --- FUNÇÕES DE CONEXÃO INTELIGENTE ---
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        # Modo Produção: Postgres
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = DictCursor
        return conn, '%s'
    else:
        # Modo Local: SQLite
        conn = sqlite3.connect('kumbuflow.db')
        conn.row_factory = sqlite3.Row
        return conn, '?'

def query_db(query, args=(), one=False):
    """Para SELECT (Leitura)"""
    conn, placeholder = get_db_connection()
    # Converte '?' para '%s' se for Postgres
    query = query.replace('?', placeholder)
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv
# Adiciona isto no teu sistema.py, logo após o app = Flask(__name__)

def formatar_moeda(valor):
    # Isto assume que o valor é um número. 
    # Ajusta o "Kz" ou o símbolo que quiseres usar.
    try:
        return f"Kz {float(valor):,.2f}"
    except:
        return f"Kz {valor}"

app.jinja_env.filters['moeda'] = formatar_moeda
def execute_db(query, args=()):
    """Para INSERT, UPDATE, DELETE (Escrita)"""
    conn, placeholder = get_db_connection()
    query = query.replace('?', placeholder)
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

# --- INICIALIZAÇÃO ---
def iniciar_banco_de_dados():
    # Esta função cria as tabelas apenas se estivermos em modo local (SQLite)
    # Se estiveres no Postgres (Render), as tabelas devem ser criadas via SQL
    if not os.environ.get('DATABASE_URL'):
        conn = sqlite3.connect('kumbuflow.db')
        cur = conn.cursor()
        
        # Tabelas (Mantive exatamente as tuas)
        cur.execute('''CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, nome TEXT NOT NULL, quantidade INTEGER NOT NULL, preco_custo REAL, preco_venda REAL)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS vendas (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, produto_id INTEGER, quantidade INTEGER, total REAL, lucro REAL, data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(produto_id) REFERENCES produtos(id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS fornecedores (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, nome TEXT NOT NULL, contacto TEXT, portfolio TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS encomendas (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, fornecedor_id INTEGER, produto_id INTEGER, quantidade INTEGER, data_encomenda TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(fornecedor_id) REFERENCES fornecedores(id), FOREIGN KEY(produto_id) REFERENCES produtos(id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, username TEXT UNIQUE NOT NULL, senha_hash TEXT NOT NULL, cargo TEXT, status TEXT DEFAULT 'ativo')''')
        cur.execute('''CREATE TABLE IF NOT EXISTS dividas (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, cliente TEXT NOT NULL, valor REAL NOT NULL, descricao TEXT, status TEXT DEFAULT 'Pendente', data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS despesas (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, descricao TEXT NOT NULL, valor REAL NOT NULL, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS logs_auditoria (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, acao TEXT, detalhes TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        try:
            cur.execute("ALTER TABLE usuarios ADD COLUMN status TEXT DEFAULT 'ativo';")
        except sqlite3.OperationalError:
            pass 

        cur.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        if not cur.fetchone():
            senha_admin = generate_password_hash('admin123')
            cur.execute("INSERT INTO usuarios (nome, username, senha_hash, cargo, status) VALUES (?, ?, ?, ?, 'ativo')", ('Administrador', 'admin', senha_admin, 'admin'))
        conn.commit()
        conn.close()

iniciar_banco_de_dados()

def registar_log(usuario, acao, detalhes=None):
    execute_db("INSERT INTO logs_auditoria (usuario, acao, detalhes) VALUES (?, ?, ?)", (usuario, acao, detalhes))

@app.before_request
def verificar_acesso():
    if request.endpoint not in ['login', 'static', 'debug_usuarios'] and 'usuario_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('senha')
        utilizador = query_db("SELECT * FROM usuarios WHERE username = ?", (username,), one=True)
        
        if utilizador and check_password_hash(utilizador['senha_hash'], senha):
            status_atual = utilizador['status'] if utilizador['status'] else 'ativo'
            if status_atual == 'suspenso':
                flash("A sua conta está SUSPENSA!", "error")
                return redirect(url_for('login'))
            session['usuario_id'] = utilizador['id']
            session['nome'] = utilizador['nome']
            session['cargo'] = utilizador['cargo']
            registar_log(utilizador['nome'], "Login", "Entrou no sistema.")
            return redirect(url_for('dashboard'))
        else:
            flash("Utilizador ou senha incorretos!", "error")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    usuario_logado = session.get('usuario_id')
    # Atenção: No Postgres, funções como strftime podem variar. Se erro, usa to_char(data_venda, 'YYYY-MM')
    dados_vendas = query_db('''SELECT SUM(total) as faturacao, SUM(lucro) as lucro_bruto, COUNT(id) as total_vendas 
                              FROM vendas WHERE usuario_id = ?''', (usuario_logado,), one=True)
    
    faturacao = dados_vendas['faturacao'] if dados_vendas['faturacao'] else 0.0
    lucro_bruto = dados_vendas['lucro_bruto'] if dados_vendas['lucro_bruto'] else 0.0
    total_vendas = dados_vendas['total_vendas'] if dados_vendas['total_vendas'] else 0

    faturacao_mensal = query_db('''SELECT SUM(total) as faturacao_mensal FROM vendas 
                                   WHERE usuario_id = ? AND strftime('%Y-%m', data_venda) = strftime('%Y-%m', 'now')''', (usuario_logado,), one=True)
    faturacao_mensal = faturacao_mensal['faturacao_mensal'] if faturacao_mensal and faturacao_mensal['faturacao_mensal'] else 0.0

    total_despesas = query_db("SELECT SUM(valor) as total_despesas FROM despesas WHERE usuario_id = ?", (usuario_logado,), one=True)
    total_despesas = total_despesas['total_despesas'] if total_despesas and total_despesas['total_despesas'] else 0.0
    lucro_real = lucro_bruto - total_despesas

    top_produtos = query_db('''SELECT p.nome, SUM(v.quantidade) as qtd_vendida, SUM(v.total) as total_faturado 
                               FROM vendas v JOIN produtos p ON v.produto_id = p.id
                               WHERE v.usuario_id = ? GROUP BY p.nome ORDER BY qtd_vendida DESC LIMIT 5''', (usuario_logado,))
    alertas_stock = query_db("SELECT nome, quantidade FROM produtos WHERE usuario_id = ? AND quantidade <= 5", (usuario_logado,))

    return render_template('dashboard.html', faturacao=faturacao, faturacao_mensal=faturacao_mensal, lucro=lucro_real, 
                           total_despesas=total_despesas, total_vendas=total_vendas, top_produtos=top_produtos, alertas_stock=alertas_stock)

@app.route('/gestao_stock', methods=['GET', 'POST'])
def gestao_stock():
    usuario_logado = session.get('usuario_id')
    if request.method == 'POST':
        acao = request.form.get('acao')
        if acao == 'adicionar':
            execute_db('''INSERT INTO produtos (usuario_id, nome, quantidade, preco_custo, preco_venda) VALUES (?, ?, ?, ?, ?)''', 
                       (usuario_logado, request.form.get('nome'), int(request.form.get('quantidade')), float(request.form.get('preco_custo')), float(request.form.get('preco_venda'))))
            registar_log(session.get('nome'), "Adicionar Produto", f"Adicionado {request.form.get('nome')}.")
            flash("Produto adicionado!", "success")
        elif acao == 'eliminar':
            execute_db("DELETE FROM produtos WHERE id = ? AND usuario_id = ?", (request.form.get('produto_id'), usuario_logado))
            flash("Produto eliminado!", "success")
        return redirect(url_for('gestao_stock'))
    produtos = query_db("SELECT * FROM produtos WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    return render_template('gestao_stock.html', produtos=produtos)

@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    usuario_logado = session.get('usuario_id')
    if request.method == 'POST':
        p_id = request.form.get('produto_id')
        qtd = int(request.form.get('quantidade'))
        produto = query_db("SELECT * FROM produtos WHERE id = ? AND usuario_id = ?", (p_id, usuario_logado), one=True)
        if produto and produto['quantidade'] >= qtd:
            execute_db("UPDATE produtos SET quantidade = ? WHERE id = ?", (produto['quantidade'] - qtd, p_id))
            execute_db("INSERT INTO vendas (usuario_id, produto_id, quantidade, total, lucro) VALUES (?, ?, ?, ?, ?)", 
                       (usuario_logado, p_id, qtd, produto['preco_venda'] * qtd, (produto['preco_venda'] - produto['preco_custo']) * qtd))
            flash("Venda realizada!", "success")
        else:
            flash("Stock insuficiente!", "error")
        return redirect(url_for('vendas'))
    produtos = query_db("SELECT * FROM produtos WHERE quantidade > 0 AND usuario_id = ? ORDER BY nome ASC", (usuario_logado,))
    ultimas_vendas = query_db('''SELECT v.id, p.nome as produto, v.quantidade, v.total, v.data_venda FROM vendas v 
                                 JOIN produtos p ON v.produto_id = p.id WHERE v.usuario_id = ? ORDER BY v.id DESC LIMIT 10''', (usuario_logado,))
    return render_template('vendas.html', produtos=produtos, vendas=ultimas_vendas)

@app.route('/fornecedores', methods=['GET', 'POST'])
def fornecedores():
    usuario_logado = session.get('usuario_id')
    if request.method == 'POST':
        if request.form.get('acao') == 'adicionar':
            execute_db("INSERT INTO fornecedores (usuario_id, nome, contacto, portfolio) VALUES (?, ?, ?, ?)", 
                       (usuario_logado, request.form.get('nome'), request.form.get('contacto'), request.form.get('portfolio')))
        elif request.form.get('acao') == 'eliminar':
            execute_db("DELETE FROM fornecedores WHERE id = ? AND usuario_id = ?", (request.form.get('fornecedor_id'), usuario_logado))
        return redirect(url_for('fornecedores'))
    lista = query_db("SELECT * FROM fornecedores WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    return render_template('fornecedores.html', fornecedores=lista)

@app.route('/auditoria')
def auditoria():
    if session.get('cargo') != 'admin': return redirect(url_for('dashboard'))
    logs = query_db("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 100")
    return render_template('auditoria.html', logs=logs)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('cargo') != 'admin': return redirect(url_for('dashboard'))
    if request.method == 'POST':
        if request.form.get('acao') == 'adicionar':
            execute_db("INSERT INTO usuarios (nome, username, senha_hash, cargo, status) VALUES (?, ?, ?, ?, 'ativo')", 
                       (request.form.get('nome'), request.form.get('username'), generate_password_hash(request.form.get('senha')), request.form.get('cargo')))
        elif request.form.get('acao') == 'alternar_status':
            execute_db("UPDATE usuarios SET status = ? WHERE id = ?", ('suspenso' if request.form.get('status_atual') == 'ativo' else 'ativo', request.form.get('user_id')))
        return redirect(url_for('admin'))
    equipa = query_db("SELECT id, nome, username, cargo, status FROM usuarios ORDER BY id DESC")
    return render_template('admin.html', equipa=equipa)

@app.route('/despesas', methods=['GET', 'POST'])
def despesas():
    usuario_logado = session.get('usuario_id')
    if request.method == 'POST':
        execute_db("INSERT INTO despesas (usuario_id, descricao, valor) VALUES (?, ?, ?)", (usuario_logado, request.form.get('descricao'), float(request.form.get('valor'))))
        return redirect(url_for('despesas'))
    lista_despesas = query_db("SELECT * FROM despesas WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    return render_template('despesas.html', despesas=lista_despesas)

@app.route('/dividas', methods=['GET', 'POST'])
def dividas():
    usuario_logado = session.get('usuario_id')
    if request.method == 'POST':
        if request.form.get('acao') == 'adicionar':
            execute_db("INSERT INTO dividas (usuario_id, cliente, valor, descricao) VALUES (?, ?, ?, ?)", (usuario_logado, request.form.get('cliente'), float(request.form.get('valor')), request.form.get('descricao')))
        elif request.form.get('acao') == 'pagar':
            execute_db("UPDATE dividas SET status = 'Pago' WHERE id = ? AND usuario_id = ?", (request.form.get('divida_id'), usuario_logado))
        return redirect(url_for('dividas'))
    lista_dividas = query_db("SELECT * FROM dividas WHERE usuario_id = ? ORDER BY status DESC, id DESC", (usuario_logado,))
    return render_template('dividas.html', dividas=lista_dividas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=5050, debug=True)
