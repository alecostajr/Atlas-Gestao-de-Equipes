import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# ==========================================================
# CONFIGURAÇÕES DE SEGURANÇA E SERVIÇOS
# ==========================================================
# Chave da API do Gemini protegida no servidor
API_KEY_GEMINI = os.getenv('GEMINI_API_KEY', 'AQ.Ab8RN6LrPKRMHw6ixKSkvHTfht6wYWsJInPx_c42v_eRQcB0Fw')
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY_GEMINI}"

# Configurações de e-mail SMTP (Gmail)
# DICA: Para o Gmail, gere uma "Senha de App" de 16 dígitos em Conta Google > Segurança
EMAIL_REMETENTE = os.getenv('MAIL_USER', 'seu_email@gmail.com')
SENHA_APP_EMAIL = os.getenv('MAIL_PASS', 'sua_senha_de_app_aqui')

# Banco de dados em memória (inicializado com conta Administrador pré-definida)
usuarios_db = {
    "admin": {
        "email": "admin@financeai.com",
        "password": "admin",
        "role": "admin",
        "transactions": [
            {"id": 1, "desc": "Assinatura Servidor Cloud", "val": 180.00, "date": "2026-10-01", "cat": "Infraestrutura", "type": "saida"},
            {"id": 2, "desc": "Venda de Licença Pro", "val": 1200.00, "date": "2026-10-05", "cat": "Salário/Renda", "type": "entrada"}
        ]
    }
}

def enviar_email_confirmacao(email_destinatario, nome_usuario):
    """Envia e-mail de confirmação via servidor SMTP seguro do Gmail."""
    if not EMAIL_REMETENTE or 'seu_email' in EMAIL_REMETENTE:
        print("[Aviso] Credenciais de e-mail não configuradas no app.py. E-mail simulado.")
        return False

    msg = MIMEMultipart()
    msg['From'] = EMAIL_REMETENTE
    msg['To'] = email_destinatario
    msg['Subject'] = "Confirmação de Registo - FinanceAI"

    corpo = f"""Olá, {nome_usuario}!

Seja bem-vindo(a) ao FinanceAI!

Sua conta foi criada com sucesso e você já pode organizar suas finanças com o auxílio do nosso assistente de IA.

Atenciosamente,
Equipe FinanceAI
"""
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_REMETENTE, SENHA_APP_EMAIL)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[Erro SMTP] Falha ao enviar e-mail: {e}")
        return False

# ==========================================================
# ROTAS DE AUTENTICAÇÃO
# ==========================================================
@app.route('/api/register', methods=['POST'])
def registrar():
    dados = request.get_json() or {}
    usuario = dados.get('username', '').strip()
    email = dados.get('email', '').strip()
    senha = dados.get('password', '').strip()

    if not usuario or not senha or not email:
        return jsonify({"erro": "Todos os campos (utilizador, e-mail e senha) são obrigatórios."}), 400

    if usuario in usuarios_db:
        return jsonify({"erro": "Este nome de utilizador já está cadastrado."}), 409

    # Novos utilizadores são sempre cadastrados como "user"
    usuarios_db[usuario] = {
        "email": email,
        "password": senha,
        "role": "user",
        "transactions": []
    }

    email_enviado = enviar_email_confirmacao(email, usuario)
    msg = "Registo concluído!"
    if email_enviado:
        msg += " Um e-mail de confirmação foi enviado para " + email
    else:
        msg += " (E-mail não disparado. Configure as credenciais SMTP no app.py se desejar o envio real)."

    return jsonify({"mensagem": msg}), 201

@app.route('/api/login', methods=['POST'])
def login():
    dados = request.get_json() or {}
    usuario = dados.get('username', '').strip()
    senha = dados.get('password', '').strip()

    if not usuario or not senha:
        return jsonify({"erro": "Informe utilizador e senha."}), 400

    conta = usuarios_db.get(usuario)
    if conta and conta['password'] == senha:
        return jsonify({
            "mensagem": "Autenticado com sucesso",
            "username": usuario,
            "role": conta['role'],
            "transactions": conta.get('transactions', [])
        }), 200

    return jsonify({"erro": "Utilizador ou senha incorretos."}), 401

# ==========================================================
# ROTA ADMINISTRATIVA (Lista de Contas)
# ==========================================================
@app.route('/api/admin/users', methods=['GET'])
def listar_usuarios():
    # Em produção, autentique um token JWT / Header de permissão aqui
    lista = [
        {
            "username": u,
            "email": dados.get("email", ""),
            "role": dados.get("role", "user"),
            "total_transacoes": len(dados.get("transactions", []))
        }
        for u, dados in usuarios_db.items()
    ]
    return jsonify({"usuarios": lista}), 200

# ==========================================================
# ROTA DO AGENTE DE IA (Gemini)
# ==========================================================
@app.route('/api/consultor', methods=['POST'])
def consultor_ia():
    dados = request.get_json() or {}
    usuario = dados.get('username', 'Usuário')
    pergunta = dados.get('question', '').strip()
    transacoes = dados.get('transactions', [])

    if not pergunta:
        return jsonify({"erro": "Pergunta não informada."}), 400

    transacoes_texto = json.dumps(transacoes, ensure_ascii=False)

    prompt = f"""
    Você é um consultor financeiro virtual inteligente e analítico, operando dentro de um sistema de finanças pessoais com tema cyberpunk/tecnológico.
    O nome do usuário é: {usuario}.
    
    Aqui está a lista completa de transações cadastradas na conta dele (formato JSON):
    {transacoes_texto}
    
    Com base exclusivamente nesses dados e em boas práticas de planejamento e metas de economia, responda à pergunta do usuário de forma amigável, clara, concisa e direta ao ponto (máximo de 2 parágrafos).
    
    Pergunta do usuário: "{pergunta}"
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        resposta_ia = data['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"resposta": resposta_ia}), 200
    except requests.exceptions.RequestException as e:
        print(f"[Erro Gemini API]: {e}")
        return jsonify({"erro": "Falha na comunicação com o serviço de IA. Verifique a chave de API."}), 502

if __name__ == '__main__':
    print("Iniciando servidor FinanceAI...")
    print("Contas de teste padrão:")
    print(" - Administrador: user='admin' / senha='admin'")
    app.run(debug=True, port=5000)
