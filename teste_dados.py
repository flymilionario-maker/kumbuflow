import sqlite3
conn = sqlite3.connect('kumbuflow.db')
cur = conn.cursor()

# 1. Adicionar um produto
cur.execute("INSERT INTO produtos (nome, quantidade, preco_custo, preco_venda) VALUES ('Router TP-Link', 20, 5000, 8500)")
# 2. Adicionar uma venda
cur.execute("INSERT INTO vendas (produto_id, quantidade, total, lucro) VALUES (1, 2, 17000, 7000)")

conn.commit()
conn.close()
print("Dados injetados com sucesso! Atualiza o Dashboard.")