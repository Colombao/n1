from flask import Flask, render_template, flash, redirect, url_for, request, get_flashed_messages, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_principal import Principal, Permission, RoleNeed, identity_loaded, UserNeed, Identity, AnonymousIdentity, identity_changed


app = Flask(__name__)
app.secret_key = 'senha secreta dos cookies 😎'


# Configuração do Flask-Login
login_manager = LoginManager(app)
# Definir a view de login
login_manager.login_view = "login"

principals = Principal(app)

admin_permission = Permission(RoleNeed("admin"))
user_permission = Permission(RoleNeed("user"))

users = {
    "admin": {"password": "adminpass", "role": "admin"},
    "user": {"password": "userpass", "role": "user"}
}

# Configuração do servidor de e-mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'seuemail@gmail.com'
app.config['MAIL_PASSWORD'] = 'sua key do email'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

# Serializador para gerar os tokens seguros
s = URLSafeTimedSerializer(app.secret_key)

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

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if current_user.is_authenticated: # Verifica se o usuário está autenticado
        identity.provides.add(UserNeed(current_user.id)) # Adiciona o ID do usuário à identidade
        identity.provides.add(RoleNeed(current_user.role))

@app.route('/users')
def users():
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=2)
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

# Rota para solicitar redefinição de senha
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        # Aqui vocês irão verificar no BD se o email recebido é válido,
        email_exists = User.query.filter_by(login=email).first()
        # ou seja, se é um usuário do sistema
        if not email_exists:
            flash('Email inválido', category='danger')
            return jsonify({"message": "E-mail não encontrado na base de dados.", "status": "danger"}), 404

        token = s.dumps(email, salt='password_recovery')
        msg = Message('Redefinição de Senha',sender='joaoocolombo@gmail.com', recipients=[email])

        link = url_for('reset_password', token=token, _external=True)
        msg.body = f'Clique no link para redefinir a sua senha! {link}'
        mail.send(msg)

        return jsonify({"message": "E-mail enviado com sucesso.", "status": "primary"}), 200

        return  redirect(url_for('login'))

    return render_template('forgot_password.html')

# Rota para redefinir a senha
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password_recovery', max_age=3600) # 1h
    except SignatureExpired:
        return '<h1> O link de redefinição de senha expirou</h1>'
    except BadSignature:
        return '<h1>Token inválido</h1>'
    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']
        if new_password != confirm_password:
            flash('Senhas não conferem', category='danger')
            return jsonify({"message": "Senhas não conferem.", "status": "danger"}), 400
            
        user = User.query.filter_by(login=email).first()
        user.senha = generate_password_hash(new_password, method='pbkdf2:sha256')

        is_samePassword = check_password_hash(user.senha, new_password)

        db.session.commit()

        return jsonify({"message": "Senha redefinida com sucesso.", "status": "primary"}), 200

    return render_template('reset_password.html')

@app.route("/logout")
@login_required
def logout():
    logout_user() # Faz o logout do usuário
    identity_changed.send(app, identity=AnonymousIdentity()) # Atualiza a identidade para usuário anônimo
    return redirect(url_for("login"))
 
@app.route("/forbidden")
def forbidden():
    return render_template("403.html"), 403

@app.route('/home')
def dashboard():
    return render_template('home.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
