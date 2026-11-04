# Estoque Fácil — MVP acadêmico

Aplicação web para controle de estoque de uma loja de roupas, desenvolvida como projeto acadêmico de ADS. Implementa login, cadastro de produtos por tamanho/cor, consulta de saldos, entradas/saídas e alertas de estoque baixo.

## Stack
Python 3.12, Flask 3.1.x, SQLite, HTML/CSS e pytest.

## Executar localmente

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
# Windows PowerShell, escolha um valor longo e aleatório:
$env:SECRET_KEY = "substitua-por-um-segredo-longo-aleatorio"
python -m flask --app app:create_app init-db
python -m flask --app app:create_app criar-admin
python -m flask --app app:create_app run
```

Abra http://127.0.0.1:5000 e entre com o usuário criado. O banco será criado na pasta `instance/`, ignorada pelo Git. **Nunca publique banco, senhas, chaves ou dados reais.**

## Testes

```bash
python -m pytest -q
```

O workflow `.github/workflows/tests.yml` executa os testes a cada push e pull request.

## Limites

Projeto educacional, não homologado para uso comercial. A interface demonstra o fluxo principal, mas ainda exige validação externa, testes de acessibilidade, avaliação de desempenho, reforço de autenticação (limitação de tentativas e controle de perfis) e configuração de HTTPS e hospedagem persistente antes de produção. Não existe integração com MarketUP.

## Organização

- `app.py`: rotas, autenticação, banco e regras de estoque
- `templates/`: páginas HTML
- `static/`: interface e responsividade
- `tests/`: verificações automatizadas
- `.github/workflows/`: integração contínua

## Fluxo de Git sugerido

1. Criar repositório público `estoque-facil-mvp` no GitHub.
2. Publicar a branch `main` com o projeto.
3. Criar uma branch `feature/melhorias-estoque`, fazer uma alteração real, abrir Pull Request e documentar a revisão antes do merge.

Licença: uso educacional.
