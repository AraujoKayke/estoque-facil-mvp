"""Estoque Fácil: MVP educacional de controle de estoque."""
import os
import sqlite3
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
 id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE,
 senha_hash TEXT NOT NULL, perfil TEXT NOT NULL DEFAULT 'FUNCIONARIO', ativo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS produtos (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, categoria TEXT NOT NULL,
 tamanho TEXT NOT NULL, cor TEXT NOT NULL,
 quantidade INTEGER NOT NULL DEFAULT 0 CHECK(quantidade >= 0),
 estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK(estoque_minimo >= 0),
 UNIQUE(nome, tamanho, cor)
);
CREATE TABLE IF NOT EXISTS movimentacoes (
 id INTEGER PRIMARY KEY, produto_id INTEGER NOT NULL REFERENCES produtos(id) ON DELETE RESTRICT,
 tipo TEXT NOT NULL CHECK(tipo IN ('ENTRADA','SAIDA')),
 quantidade INTEGER NOT NULL CHECK(quantidade > 0),
 observacao TEXT NOT NULL DEFAULT '',
 data_hora TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mov_produto ON movimentacoes(produto_id);
"""

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY'), DATABASE=str(Path(app.instance_path)/'estoque.sqlite3'), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('FLASK_SECURE_COOKIE') == '1')
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
            g.db.execute('PRAGMA busy_timeout=10000')
        return g.db

    @app.teardown_appcontext
    def close_db(exc):
        conn = g.pop('db', None)
        if conn is not None:
            conn.close()

    def init_db():
        db().executescript(SCHEMA)
        db().commit()

    app.init_db = init_db

    def signed_in(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not session.get('uid'):
                return redirect(url_for('login'))
            user = db().execute('SELECT id FROM usuarios WHERE id=? AND ativo=1', (session['uid'],)).fetchone()
            if not user:
                session.clear()
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapper

    def token():
        if 'csrf' not in session:
            session['csrf'] = os.urandom(24).hex()
        return session['csrf']

    @app.context_processor
    def inject_csrf():
        return {'csrf_token':token}

    @app.before_request
    def csrf_protect():
        if request.method == 'POST':
            import hmac
            if not hmac.compare_digest(session.get('csrf', ''), request.form.get('csrf_token', '')) or not session.get('csrf'):
                abort(400, description='Token de formulário inválido. Atualize a página.')

    @app.get('/')
    def home():
        return redirect(url_for('produtos') if session.get('uid') else url_for('login'))

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method == 'POST':
            login_value = request.form.get('login','').strip()
            password = request.form.get('senha','')
            user = db().execute('SELECT * FROM usuarios WHERE login=? AND ativo=1', (login_value,)).fetchone()
            if user and check_password_hash(user['senha_hash'], password):
                session.clear()
                session['uid'] = user['id']
                session['login'] = user['login']
                token()
                return redirect(url_for('produtos'))
            flash('Usuário ou senha inválidos.', 'erro')
        return render_template('login.html')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/produtos')
    @signed_in
    def produtos():
        busca = request.args.get('busca','').strip()
        rows = db().execute('SELECT * FROM produtos WHERE nome LIKE ? ORDER BY nome, tamanho, cor LIMIT 500', ('%'+busca+'%',)).fetchall()
        total = db().execute('SELECT COUNT(*) n, COALESCE(SUM(quantidade),0) unidades, COALESCE(SUM(quantidade<=estoque_minimo),0) baixos FROM produtos').fetchone()
        return render_template('produtos.html', produtos=rows, total=total, busca=busca)

    @app.post('/produtos')
    @signed_in
    def criar_produto():
        nome = request.form.get('nome','').strip()
        categoria = request.form.get('categoria','').strip()
        tamanho = request.form.get('tamanho','').strip()
        cor = request.form.get('cor','').strip()
        try:
            qtd = int(request.form.get('quantidade',''))
            minimo = int(request.form.get('estoque_minimo',''))
        except ValueError:
            flash('Quantidades precisam ser números inteiros.', 'erro')
            return redirect(url_for('produtos'))
        if not all((nome,categoria,tamanho,cor)) or any(len(s)>120 for s in (nome,categoria,tamanho,cor)) or qtd<0 or minimo<0:
            flash('Informe os campos obrigatórios com quantidades não negativas.', 'erro')
            return redirect(url_for('produtos'))
        try:
            conn = db()
            conn.execute('INSERT INTO produtos(nome,categoria,tamanho,cor,quantidade,estoque_minimo) VALUES (?,?,?,?,?,?)', (nome,categoria,tamanho,cor,qtd,minimo))
            conn.commit()
            flash('Produto cadastrado com sucesso.', 'sucesso')
        except sqlite3.IntegrityError:
            flash('Já existe um produto com esse nome, tamanho e cor.', 'erro')
        return redirect(url_for('produtos'))

    @app.route('/movimentacoes', methods=['GET','POST'])
    @signed_in
    def movimentacoes():
        conn=db()
        if request.method == 'POST':
            try:
                pid=int(request.form.get('produto_id',''))
                qtd=int(request.form.get('quantidade',''))
            except ValueError:
                flash('Selecione um produto e informe uma quantidade inteira.', 'erro')
                return redirect(url_for('movimentacoes'))
            tipo=request.form.get('tipo','')
            obs=request.form.get('observacao','').strip()
            if qtd<=0 or tipo not in ('ENTRADA','SAIDA') or len(obs)>300:
                flash('Movimentação inválida.', 'erro')
                return redirect(url_for('movimentacoes'))
            try:
                conn.execute('BEGIN IMMEDIATE')
                produto=conn.execute('SELECT quantidade FROM produtos WHERE id=?',(pid,)).fetchone()
                if not produto:
                    conn.rollback()
                    flash('Produto não encontrado.', 'erro')
                    return redirect(url_for('movimentacoes'))
                novo=produto['quantidade']+(qtd if tipo=='ENTRADA' else -qtd)
                if novo<0:
                    conn.rollback()
                    flash('Quantidade insuficiente em estoque.', 'erro')
                    return redirect(url_for('movimentacoes'))
                conn.execute('UPDATE produtos SET quantidade=? WHERE id=?',(novo,pid))
                conn.execute('INSERT INTO movimentacoes(produto_id,tipo,quantidade,observacao) VALUES (?,?,?,?)',(pid,tipo,qtd,obs))
                conn.commit()
                flash(f'{tipo.title()} registrada com sucesso. Novo saldo: {novo}.', 'sucesso')
            except Exception:
                conn.rollback()
                raise
            return redirect(url_for('movimentacoes'))
        products=conn.execute('SELECT * FROM produtos ORDER BY nome, tamanho').fetchall()
        history=conn.execute('SELECT m.*, p.nome,p.tamanho,p.cor FROM movimentacoes m JOIN produtos p ON p.id=m.produto_id ORDER BY m.id DESC LIMIT 20').fetchall()
        return render_template('movimentacoes.html', produtos=products, historico=history)

    @app.cli.command('init-db')
    def init_db_command():
        init_db()
        print('Banco de dados criado.')

    @app.cli.command('criar-admin')
    def create_admin_command():
        import getpass
        init_db()
        login_value=input('Login administrador: ').strip()
        password=getpass.getpass('Senha (mínimo 12 caracteres): ')
        if len(password)<12 or not login_value:
            raise SystemExit('Informe login e senha de pelo menos 12 caracteres.')
        db().execute('INSERT INTO usuarios(login,senha_hash,perfil) VALUES (?,?,?)',(login_value,generate_password_hash(password,method='scrypt'),'ADMIN'))
        db().commit()
        print('Administrador criado.')

    return app

if __name__ == '__main__':
    app=create_app()
    if not app.config['SECRET_KEY']:
        raise SystemExit('Defina SECRET_KEY no ambiente antes de executar.')
    app.run(debug=False)
