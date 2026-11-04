import pytest
from werkzeug.security import generate_password_hash
from app import create_app

@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING':True, 'SECRET_KEY':'test-only-secret', 'DATABASE':str(tmp_path/'test.sqlite3')})
    with app.app_context():
        app.init_db()
        from flask import g
        g.db.execute('INSERT INTO usuarios(login,senha_hash,perfil) VALUES (?,?,?)',('teste',generate_password_hash('senha-super-segura',method='scrypt'),'ADMIN'))
        g.db.commit()
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth(client):
    client.get('/login')
    with client.session_transaction() as sess: csrf=sess['csrf']
    r=client.post('/login',data={'login':'teste','senha':'senha-super-segura','csrf_token':csrf},follow_redirects=True)
    assert r.status_code==200
    return client

def csrf(client):
    with client.session_transaction() as sess: return sess['csrf']
