from flask import g

def csrf(client):
    with client.session_transaction() as sess: return sess['csrf']

def product(client,qty=10):
    return client.post('/produtos',data={'nome':'Camiseta','categoria':'Roupa','tamanho':'M','cor':'Preta','quantidade':str(qty),'estoque_minimo':'5','csrf_token':csrf(client)},follow_redirects=True)

def move(client,tipo,qtd):
    return client.post('/movimentacoes',data={'produto_id':'1','tipo':tipo,'quantidade':str(qtd),'csrf_token':csrf(client)},follow_redirects=True)

def test_requires_login(client):
    assert client.get('/produtos').status_code==302
    assert client.get('/movimentacoes').status_code==302

def test_invalid_login(client):
    client.get('/login')
    r=client.post('/login',data={'login':'teste','senha':'errada','csrf_token':csrf(client)},follow_redirects=True)
    assert 'inválidos'.encode() in r.data

def test_product_creation_and_low_stock(auth):
    r=product(auth,4)
    assert 'Camiseta'.encode() in r.data
    assert 'Estoque baixo'.encode() in r.data
    assert 'cadastrado com sucesso'.encode() in r.data

def test_duplicate_product_rejected(auth):
    product(auth)
    r=product(auth)
    assert 'Já existe'.encode() in r.data

def test_movement_updates_balance(auth,app):
    product(auth,15)
    assert b'Novo saldo: 12' in move(auth,'SAIDA',3).data
    with app.app_context():
        from sqlite3 import connect
        with connect(app.config['DATABASE']) as db:
            assert db.execute('SELECT quantidade FROM produtos WHERE id=1').fetchone()[0]==12
            assert db.execute('SELECT COUNT(*) FROM movimentacoes').fetchone()[0]==1

def test_negative_stock_blocked_atomically(auth,app):
    product(auth,4)
    assert 'Quantidade insuficiente'.encode() in move(auth,'SAIDA',5).data
    from sqlite3 import connect
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT quantidade FROM produtos WHERE id=1').fetchone()[0]==4
        assert db.execute('SELECT COUNT(*) FROM movimentacoes').fetchone()[0]==0

def test_zero_quantity_rejected(auth):
    product(auth)
    assert 'inválida'.encode() in move(auth,'ENTRADA',0).data

def test_csrf_required(auth):
    assert auth.post('/produtos',data={'nome':'X'}).status_code==400

def test_logout_blocks_access(auth):
    auth.post('/logout',data={'csrf_token':csrf(auth)})
    assert auth.get('/produtos').status_code==302
