from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
import datetime

app = Flask(__name__)
app.secret_key = 'kumbuflow_secret'

def iniciar_banco_de_dados():
    conn = sqlite3.connect('kumbuflow.db')
    cur = conn.cursor()
    
    # 1. Tabela de Produtos
    cur.execute('''CREATE TABLE IF NOT EXISTS produtos 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   usuario_id INTEGER,
                   nome TEXT NOT NULL, 
                   quantidade INTEGER NOT NULL, 
                   preco_custo REAL, 
                   preco_venda REAL)''')
    
    # 2. Tabela de Vendas
    cur.execute('''CREATE TABLE IF NOT EXISTS vendas 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   usuario_id INTEGER,
                   produto_id INTEGER, 
                   quantidade INTEGER, 
                   total REAL, 
                   lucro REAL, 
                   data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   FOREIGN KEY(produto_id) REFERENCES produtos(id))''')
    
    # 3. Tabela de Fornecedores
    cur.execute('''CREATE TABLE IF NOT EXISTS fornecedores 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   usuario_id INTEGER,
                   nome TEXT NOT NULL, 
                   contacto TEXT, 
                   portfolio TEXT)''')
    
    # 4. Tabela de Encomendas
    cur.execute('''CREATE TABLE IF NOT EXISTS encomendas 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   usuario_id INTEGER,
                   fornecedor_id INTEGER, 
                   produto_id INTEGER, 
                   quantidade INTEGER, 
                   data_encomenda TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                   FOREIGN KEY(fornecedor_id) REFERENCES fornecedores(id),
                   FOREIGN KEY(produto_id) REFERENCES produtos(id))''')

    # 5. Tabela de Usuários
    cur.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   nome TEXT NOT NULL, 
                   username TEXT UNIQUE NOT NULL, 
                   senha_hash TEXT NOT NULL, 
                   cargo TEXT, 
                   status TEXT DEFAULT 'ativo')''')

    # 6. Tabela de Dívidas (Nova)
    cur.execute('''CREATE TABLE IF NOT EXISTS dividas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        cliente TEXT NOT NULL,
        valor REAL NOT NULL,
        descricao TEXT,
        status TEXT DEFAULT 'Pendente',
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )''')

    # 7. Tabela de Despesas (Nova)
    cur.execute('''CREATE TABLE IF NOT EXISTS despesas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        descricao TEXT NOT NULL,
        valor REAL NOT NULL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
    )''')

    # Correção para garantir a coluna status em bases antigas
    try:
        cur.execute("ALTER TABLE usuarios ADD COLUMN status TEXT DEFAULT 'ativo';")
    except sqlite3.OperationalError:
        pass 

    # 8. Tabela de Logs
    cur.execute('''CREATE TABLE IF NOT EXISTS logs_auditoria 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT, 
                   acao TEXT, detalhes TEXT, data TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Criar admin inicial caso não exista
    cur.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not cur.fetchone():
        senha_admin = generate_password_hash('admin123')
        cur.execute("INSERT INTO usuarios (nome, username, senha_hash, cargo, status) VALUES (?, ?, ?, ?, 'ativo')", 
                    ('Administrador', 'admin', senha_admin, 'admin'))

    conn.commit()
    conn.close()

# Inicializa o banco ao rodar o script
iniciar_banco_de_dados()

def registar_log(usuario, acao, detalhes=None):
    try:
        conn = sqlite3.connect('kumbuflow.db')
        conn.execute("INSERT INTO logs_auditoria (usuario, acao, detalhes) VALUES (?, ?, ?)", (usuario, acao, detalhes))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao logar: {e}")

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
        
        conn = sqlite3.connect('kumbuflow.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        utilizador = cur.fetchone()
        conn.close()
        
        if utilizador and check_password_hash(utilizador['senha_hash'], senha):
            status_atual = utilizador['status'] if utilizador['status'] else 'ativo'
            
            if status_atual == 'suspenso':
                flash("A sua conta está SUSPENSA por falta de pagamento! Contacte o administrador.", "error")
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
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Faturamento e Lucro Bruto das Vendas
    cur.execute('''SELECT 
                    SUM(total) as faturacao, 
                    SUM(lucro) as lucro_bruto,
                    COUNT(id) as total_vendas 
                   FROM vendas WHERE usuario_id = ?''', (usuario_logado,))
    dados_vendas = cur.fetchone()
    
    faturacao = dados_vendas['faturacao'] if dados_vendas['faturacao'] else 0.0
    lucro_bruto = dados_vendas['lucro_bruto'] if dados_vendas['lucro_bruto'] else 0.0
    total_vendas = dados_vendas['total_vendas'] if dados_vendas['total_vendas'] else 0

    # 2. Faturamento Mensal (Apenas o mês atual)
    cur.execute('''SELECT SUM(total) as faturacao_mensal FROM vendas 
                   WHERE usuario_id = ? AND strftime('%Y-%m', data_venda) = strftime('%Y-%m', 'now')''', (usuario_logado,))
    faturacao_mensal = cur.fetchone()['faturacao_mensal']
    faturacao_mensal = faturacao_mensal if faturacao_mensal else 0.0

    # 3. Total de Despesas (O que saiu do caixa)
    cur.execute("SELECT SUM(valor) as total_despesas FROM despesas WHERE usuario_id = ?", (usuario_logado,))
    total_despesas = cur.fetchone()['total_despesas']
    total_despesas = total_despesas if total_despesas else 0.0

    # 4. LUCRO ESTIMADO REAL (Lucro bruto - Despesas)
    lucro_real = lucro_bruto - total_despesas

    # 5. Top produtos
    cur.execute('''SELECT p.nome, SUM(v.quantidade) as qtd_vendida, SUM(v.total) as total_faturado 
                   FROM vendas v 
                   JOIN produtos p ON v.produto_id = p.id
                   WHERE v.usuario_id = ? 
                   GROUP BY p.nome 
                   ORDER BY qtd_vendida DESC 
                   LIMIT 5''', (usuario_logado,))
    top_produtos = cur.fetchall()

    # 6. Alertas de stock
    cur.execute("SELECT nome, quantidade FROM produtos WHERE usuario_id = ? AND quantidade <= 5", (usuario_logado,))
    alertas_stock = cur.fetchall()

    conn.close()

    return render_template('dashboard.html', 
                           faturacao=faturacao, 
                           faturacao_mensal=faturacao_mensal,
                           lucro=lucro_real,                  
                           total_despesas=total_despesas,      
                           total_vendas=total_vendas, 
                           top_produtos=top_produtos, 
                           alertas_stock=alertas_stock)
@app.route('/gestao_stock', methods=['GET', 'POST'])
def gestao_stock():
    usuario_logado = session.get('usuario_id')
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'adicionar':
            nome = request.form.get('nome')
            quantidade = int(request.form.get('quantidade'))
            preco_custo = float(request.form.get('preco_custo'))
            preco_venda = float(request.form.get('preco_venda'))
            
            cur.execute('''INSERT INTO produtos (usuario_id, nome, quantidade, preco_custo, preco_venda) 
                          VALUES (?, ?, ?, ?, ?)''', (usuario_logado, nome, quantidade, preco_custo, preco_venda))
            conn.commit()
            registar_log(session.get('nome'), "Adicionar Produto", f"Produto {nome} adicionado.")
            flash("Produto adicionado com sucesso!", "success")
            
        elif acao == 'eliminar':
            produto_id = request.form.get('produto_id')
            
            cur.execute("SELECT nome FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, usuario_logado))
            produto = cur.fetchone()
            
            if produto:
                nome_produto = produto['nome']
                cur.execute("DELETE FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, usuario_logado))
                conn.commit()
                
                registar_log(session.get('nome'), "Eliminar Produto", f"Eliminou o produto: {nome_produto} (ID: {produto_id})")
                flash(f"Produto '{nome_produto}' eliminado com sucesso!", "success")
            else:
                flash("Produto não encontrado!", "error")
            
        conn.close()
        return redirect(url_for('gestao_stock'))

    cur.execute("SELECT * FROM produtos WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    produtos = cur.fetchall()
    conn.close()
    
    return render_template('gestao_stock.html', produtos=produtos)

@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
    usuario_logado = session.get('usuario_id')
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        produto_id = request.form.get('produto_id')
        quantidade_venda = int(request.form.get('quantidade'))

        cur.execute("SELECT * FROM produtos WHERE id = ? AND usuario_id = ?", (produto_id, usuario_logado))
        produto = cur.fetchone()

        if not produto:
            flash("Produto não encontrado no seu stock.", "error")
        elif produto['quantidade'] < quantidade_venda:
            flash(f"Stock insuficiente! Tem apenas {produto['quantidade']} unidades.", "error")
        else:
            total = produto['preco_venda'] * quantidade_venda
            lucro = (produto['preco_venda'] - produto['preco_custo']) * quantidade_venda
            
            novo_stock = produto['quantidade'] - quantidade_venda
            cur.execute("UPDATE produtos SET quantidade = ? WHERE id = ? AND usuario_id = ?", (novo_stock, produto_id, usuario_logado))
            
            cur.execute('''INSERT INTO vendas (usuario_id, produto_id, quantidade, total, lucro) 
                          VALUES (?, ?, ?, ?, ?)''', (usuario_logado, produto_id, quantidade_venda, total, lucro))
            conn.commit()
            
            registar_log(session.get('nome'), "Venda Realizada", f"Vendidas {quantidade_venda} un. de {produto['nome']}")
            flash(f"Venda realizada com sucesso!", "success")

        conn.close()
        return redirect(url_for('vendas'))

    cur.execute("SELECT * FROM produtos WHERE quantidade > 0 AND usuario_id = ? ORDER BY nome ASC", (usuario_logado,))
    produtos_disponiveis = cur.fetchall()

    cur.execute('''
        SELECT v.id, p.nome as produto, v.quantidade, v.total, v.data_venda 
        FROM vendas v 
        JOIN produtos p ON v.produto_id = p.id 
        WHERE v.usuario_id = ?
        ORDER BY v.id DESC LIMIT 10
    ''', (usuario_logado,))
    ultimas_vendas = cur.fetchall()
    
    conn.close()
    return render_template('vendas.html', produtos=produtos_disponiveis, vendas=ultimas_vendas)

@app.route('/fornecedores', methods=['GET', 'POST'])
def fornecedores():
    usuario_logado = session.get('usuario_id')
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'adicionar':
            nome = request.form.get('nome')
            contacto = request.form.get('contacto')
            portfolio = request.form.get('portfolio')
            
            cur.execute("INSERT INTO fornecedores (usuario_id, nome, contacto, portfolio) VALUES (?, ?, ?, ?)", 
                        (usuario_logado, nome, contacto, portfolio))
            conn.commit()
            
            registar_log(session.get('nome'), "Cadastro de Fornecedor", f"Fornecedor {nome} adicionado.")
            flash("Fornecedor registado com sucesso!", "success")
            
        elif acao == 'eliminar':
            fornecedor_id = request.form.get('fornecedor_id')
            
            cur.execute("SELECT nome FROM fornecedores WHERE id = ? AND usuario_id = ?", (fornecedor_id, usuario_logado))
            fornecedor = cur.fetchone()
            
            if fornecedor:
                nome_forn = fornecedor['nome']
                cur.execute("DELETE FROM fornecedores WHERE id = ? AND usuario_id = ?", (fornecedor_id, usuario_logado))
                conn.commit()
                
                registar_log(session.get('nome'), "Eliminar Fornecedor", f"Fornecedor '{nome_forn}' removido do sistema.")
                flash(f"Fornecedor '{nome_forn}' eliminado com sucesso!", "success")
            else:
                flash("Fornecedor não encontrado!", "error")

        conn.close()
        return redirect(url_for('fornecedores'))

    cur.execute("SELECT * FROM fornecedores WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    lista = cur.fetchall()
    conn.close()
    
    return render_template('fornecedores.html', fornecedores=lista)

@app.route('/auditoria')
def auditoria():
    if session.get('cargo') != 'admin':
        flash("Acesso restrito a administradores.", "error")
        return redirect(url_for('dashboard'))
        
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs_auditoria ORDER BY id DESC LIMIT 100")
    logs = cur.fetchall()
    conn.close()
    return render_template('auditoria.html', logs=logs)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('cargo') != 'admin':
        flash("Acesso negado!", "error")
        return redirect(url_for('dashboard'))
        
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'adicionar':
            nome = request.form.get('nome')
            username = request.form.get('username')
            senha_pura = request.form.get('senha')
            cargo = request.form.get('cargo')
            senha_criptografada = generate_password_hash(senha_pura)
            
            try:
                cur.execute("INSERT INTO usuarios (nome, username, senha_hash, cargo, status) VALUES (?, ?, ?, ?, 'ativo')", 
                            (nome, username, senha_criptografada, cargo))
                conn.commit()
                registar_log(session.get('nome'), "Criar Utilizador", f"Criou a conta de {nome}.")
                flash(f"Utilizador {nome} criado com sucesso!", "success")
            except sqlite3.IntegrityError:
                flash("Esse Nome de Utilizador já está a ser usado!", "error")
                
        elif acao == 'alternar_status':
            user_id = request.form.get('user_id')
            status_atual = request.form.get('status_atual')
            
            novo_status = 'suspenso' if status_atual == 'ativo' else 'ativo'
            cur.execute("UPDATE usuarios SET status = ? WHERE id = ?", (novo_status, user_id))
            conn.commit()
            
            tipo_log = "Suspender Conta" if novo_status == 'suspenso' else "Reativar Conta"
            registar_log(session.get('nome'), tipo_log, f"Alterou status do ID {user_id} para {novo_status}.")
            
            flash(f"Estado do utilizador updated para {novo_status.upper()}!", "success" if novo_status == 'ativo' else "error")

        conn.close()
        return redirect(url_for('admin'))

    cur.execute("SELECT id, nome, username, cargo, status FROM usuarios ORDER BY id DESC")
    equipa = cur.fetchall()
    conn.close()
    
    return render_template('admin.html', equipa=equipa)

@app.route('/debug-usuarios')
def debug_usuarios():
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios")
    users = cur.fetchall()
    conn.close()
    resultado = "<h1>Utilizadores no Banco:</h1><ul>"
    for user in users:
        resultado += f"<li>ID: {user['id']} | Nome: {user['nome']} | User: {user['username']}</li>"
    resultado += "</ul><br><a href='/login'>Voltar ao Login</a>"
    return resultado

@app.template_filter('moeda')
def formato_moeda(valor):
    try:
        if valor is None:
            valor = 0.0
        valores_americanos = f"{float(valor):,.2f}"
        valores_angolanos = valores_americanos.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{valores_angolanos} Kz"
    except (ValueError, TypeError):
        return "0,00 Kz"

@app.route('/despesas', methods=['GET', 'POST'])
def despesas():
    usuario_logado = session.get('usuario_id')
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        descricao = request.form.get('descricao')
        valor = float(request.form.get('valor'))
        
        cur.execute("INSERT INTO despesas (usuario_id, descricao, valor) VALUES (?, ?, ?)", 
                    (usuario_logado, descricao, valor))
        conn.commit()
        registar_log(session.get('nome'), "Registo de Despesa", f"Despesa de {valor} Kz: {descricao}")
        flash("Despesa registada e debitada do caixa!", "success")
        return redirect(url_for('despesas'))

    cur.execute("SELECT * FROM despesas WHERE usuario_id = ? ORDER BY id DESC", (usuario_logado,))
    lista_despesas = cur.fetchall()
    conn.close()
    return render_template('despesas.html', despesas=lista_despesas)

@app.route('/dividas', methods=['GET', 'POST'])
def dividas():
    usuario_logado = session.get('usuario_id')
    conn = sqlite3.connect('kumbuflow.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == 'POST':
        acao = request.form.get('acao')
        
        if acao == 'adicionar':
            cliente = request.form.get('cliente')
            valor = float(request.form.get('valor'))
            descricao = request.form.get('descricao')
            
            cur.execute("INSERT INTO dividas (usuario_id, cliente, valor, descricao) VALUES (?, ?, ?, ?)", 
                        (usuario_logado, cliente, valor, descricao))
            conn.commit()
            registar_log(session.get('nome'), "Registo de Dívida", f"Cliente {cliente} deve {valor} Kz")
            flash("Dívida registada com sucesso!", "success")
            
        elif acao == 'pagar':
            divida_id = request.form.get('divida_id')
            cur.execute("UPDATE dividas SET status = 'Pago' WHERE id = ? AND usuario_id = ?", (divida_id, usuario_logado))
            conn.commit()
            flash("Dívida marcada como Paga!", "success")
            
        return redirect(url_for('dividas'))

    cur.execute("SELECT * FROM dividas WHERE usuario_id = ? ORDER BY status DESC, id DESC", (usuario_logado,))
    lista_dividas = cur.fetchall()
    conn.close()
    return render_template('dividas.html', dividas=lista_dividas)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=5050, debug=True)