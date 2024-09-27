from flask import Flask, render_template, flash, redirect, url_for, request, get_flashed_messages, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(150), unique=True, nullable=False)
    senha = db.Column(db.String(150), nullable=False)
    nome_real = db.Column(db.String(150), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='ativo')  # ativo ou bloqueado
    data_atualizacao = db.Column(db.DateTime, onupdate=datetime.utcnow)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        senha = request.form['senha']
        user = User.query.filter_by(login=login).first()

        if user and check_password_hash(user.senha, senha):
            if user.status == 'bloqueado':
                return jsonify({"message": "Usuário bloqueado. Não é possível fazer login.", "status": "danger"}), 403
            else:
                return jsonify({"message": "Login realizado com sucesso!", "status": "success"}), 200
        else:
            return jsonify({"message": "Login ou senha incorretos.", "status": "danger"}), 401

    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    nome_real = request.form['nome_real']
    email = request.form['email']
    senha = request.form['senha']

    existing_user = User.query.filter_by(login=email).first()
    if existing_user:
        return jsonify({"message": "Usuário com este e-mail já existe.", "status": "danger"}), 409

    hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
    new_user = User(login=email, senha=hashed_password, nome_real=nome_real)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "Usuário cadastrado com sucesso!", "status": "success"}), 201


@app.route('/users')
def users():
    users = User.query.all()
    
    return render_template('users.html', users=users)

@app.route('/usersDesactive/<int:id>', methods=['POST'])
def deactivate_user(id):
    user = User.query.get(id)
    if user:
        user.status = "bloqueado"  # Supondo que você tenha um campo 'active' na sua model
        db.session.commit()
        return jsonify({"message": "Usuário desativado com sucesso."}), 200
    else:
        return jsonify({"message": "Usuário não encontrado."}), 404

@app.route('/usersActive/<int:id>', methods=['POST'])
def activate_user(id):
    user = User.query.get(id)
    if user:
        user.status = "ativo"
        db.session.commit()
        return jsonify({"message": "Usuário ativado com sucesso."}), 200
    else:
        return jsonify({"message": "Usuário não encontrado."}), 404

@app.route('/editUser/<int:id>', methods=['POST'])
def edit_user(id):
    print(id)
    user = User.query.get(id)
    if user:
        data = request.get_json()
        print(data)

        user.nome_real = data.get('nome_real') 
        user.login = data.get('login')

        password = data.get('senha')
        if password:
            user.senha = generate_password_hash(password, method='pbkdf2:sha256')

        db.session.commit()
        return jsonify({"message": "Usuário editado com sucesso."}), 200
    else:
        return jsonify({"message": "Usuário não encontrado."}), 404


@app.route('/home')
def dashboard():
    return render_template('home.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
