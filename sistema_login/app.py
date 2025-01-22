from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
from flask_wtf import CSRFProtect, FlaskForm, CSRFProtect
from utils.auth import admin_required, terapeuta_required
from werkzeug.utils import secure_filename
import os
from io import BytesIO
from wtforms import StringField
from wtforms.validators import DataRequired
from math import ceil
from reportlab.pdfgen import canvas
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)
app.config['SECRET_KEY'] = '1235'  # Mude para uma chave segura
app.config['UPLOAD_FOLDER'] = 'uploads/cartas_recomendacao'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB para upload
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Criar pasta de uploads se não existir
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Adicione estas configurações
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

class User(UserMixin):
    def __init__(self, id, email, tipo_usuario):
        self.id = id
        self.email = email
        self.tipo_usuario = tipo_usuario
    
    def is_admin(self):
        return self.tipo_usuario == 'admin'
    
    def is_terapeuta(self):
        return self.tipo_usuario == 'terapeuta'
    
    def is_paciente(self):
        return self.tipo_usuario == 'paciente'

def conectar_bd():
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="postgres",  # Coloque sua senha aqui se houver
            host="localhost",
            port="5432"
        )
        cur = conn.cursor()
        
        # Debug: Mostrar banco atual
        cur.execute("SELECT current_database()")
        current_db = cur.fetchone()[0]
        print(f"\nBanco atual: {current_db}")
        
        # Debug: Mostrar todas as tabelas
        cur.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        """)
        tables = cur.fetchall()
        print("Tabelas disponíveis:", tables)
        
        cur.close()
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {str(e)}")
        raise

@login_manager.user_loader
def load_user(user_id):
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute("SELECT id, email, tipo_usuario FROM usuarios WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return User(user[0], user[1], user[2])
    return None

@app.route('/')
def selecao_perfil():
    return render_template('selecao_perfil.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = conectar_bd()
        cur = conn.cursor()
        
        try:
            # Primeiro, verifica se o usuário existe e as credenciais estão corretas
            cur.execute("""
                SELECT id, email, senha, tipo_usuario 
                FROM usuarios 
                WHERE email = %s AND tipo_usuario = 'paciente' AND status = true
            """, (email,))
            
            user = cur.fetchone()
            
            if user and check_password_hash(user[2], senha):
                user_obj = User(user[0], user[1], user[3])
                login_user(user_obj)
                
                # Verifica se já existe formulário NAPESE para este usuário
                cur.execute("""
                    SELECT id FROM formulario_napese 
                    WHERE email = %s
                """, (email,))
                
                tem_formulario = cur.fetchone()
                
                if not tem_formulario:
                    # Se não tem formulário, redireciona para o formulário NAPESE
                    flash('Por favor, preencha o formulário de cadastro.', 'info')
                    return redirect(url_for('formulario_napese'))
                else:
                    # Se já tem formulário, redireciona para o dashboard
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('dashboard'))
            
            flash('Email ou senha incorretos!', 'error')
            
        except Exception as e:
            print(f"Erro no login: {str(e)}")
            flash('Erro ao realizar login. Por favor, tente novamente.', 'error')
            
        finally:
            cur.close()
            conn.close()
    
    return render_template('login.html', form=form)

@app.route('/login-terapeuta', methods=['GET', 'POST'])
def login_terapeuta():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = conectar_bd()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, email, senha, tipo_usuario 
                FROM usuarios 
                WHERE email = %s AND tipo_usuario = 'terapeuta' AND status = true
            """, (email,))
            
            user = cur.fetchone()
            
            if user and check_password_hash(user[2], senha):
                user_obj = User(user[0], user[1], user[3])
                login_user(user_obj)
                
                # Verifica se já existe formulário de cadastro para este terapeuta
                cur.execute("""
                    SELECT id FROM terapeuta_napese 
                    WHERE email = %s
                """, (email,))
                
                tem_formulario = cur.fetchone()
                
                if not tem_formulario:
                    # Se não tem formulário, redireciona para o formulário de cadastro de terapeuta
                    flash('Por favor, complete seu cadastro.', 'info')
                    return redirect(url_for('formulario_terapeuta'))
                else:
                    # Se já tem formulário, redireciona para o dashboard
                    flash('Login realizado com sucesso!', 'success')
                    return redirect(url_for('dashboard_terapeuta'))
            
            flash('Email ou senha incorretos!', 'error')
            
        except Exception as e:
            print(f"Erro no login: {str(e)}")
            flash('Erro ao realizar login. Por favor, tente novamente.', 'error')
            
        finally:
            cur.close()
            conn.close()
    
    return render_template('login_terapeuta.html', form=form)

@app.route('/login-admin', methods=['GET', 'POST'])
def login_admin():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = conectar_bd()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, email, senha, tipo_usuario 
                FROM usuarios 
                WHERE email = %s AND tipo_usuario = 'admin' AND status = true
            """, (email,))
            
            user = cur.fetchone()
            
            if user and check_password_hash(user[2], senha):
                user_obj = User(user[0], user[1], user[3])
                login_user(user_obj)
                
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('admin_usuarios'))
            
            flash('Email ou senha incorretos!', 'error')
            
        except Exception as e:
            print(f"Erro no login: {str(e)}")
            flash('Erro ao realizar login. Por favor, tente novamente.', 'error')
            
        finally:
            cur.close()
            conn.close()
    
    return render_template('login_admin.html', form=form)

@app.route('/logout')
@login_required
def logout():
    try:
        logout_user()  # Desloga o usuário
        flash('Você foi desconectado com sucesso.', 'success')
    except Exception as e:
        print(f"Erro ao realizar logout: {e}")
        flash('Ocorreu um erro ao tentar desconectar.', 'error')
    
    return redirect(url_for('selecao_perfil'))  # Redireciona para a página de login

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    form = FlaskForm()
    if request.method == 'POST':
        try:
            email = request.form['email']
            senha = request.form['senha']
            confirma_senha = request.form['confirma_senha']
            
            if senha != confirma_senha:
                flash('As senhas não coincidem!', 'error')
                return render_template('cadastro.html', form=form)
            
            conn = conectar_bd()
            cur = conn.cursor()
            
            # Verifica se o email já existe
            cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cur.fetchone():
                flash('Este email já está cadastrado!', 'error')
                cur.close()
                conn.close()
                return render_template('cadastro.html', form=form)
            
            # Gera o hash da senha
            senha_hash = generate_password_hash(senha)
            
            # Insere o usuário
            cur.execute("""
                INSERT INTO usuarios (email, senha, tipo_usuario, data_criacao, status)
                VALUES (%s, %s, 'paciente', CURRENT_TIMESTAMP, true)
                RETURNING id, email;
            """, (email, senha_hash))
            
            conn.commit()
            cur.close()
            conn.close()
            
            flash('Cadastro realizado com sucesso! Por favor, faça login para continuar.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"Erro ao cadastrar usuário: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
                cur.close()
                conn.close()
            flash('Erro ao realizar cadastro. Por favor, tente novamente.', 'error')
            return render_template('cadastro.html', form=form)
            
    return render_template('cadastro.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    return "Bem-vindo ao Dashboard!"

# Defina uma classe de formulário se ainda não tiver uma
class NapeseForm(FlaskForm):
    nome_completo = StringField('Nome Completo', validators=[DataRequired()])
    cpf = StringField('CPF', validators=[DataRequired()])
    # Adicione todos os outros campos necessários aqui
    # ...

@app.route('/formulario_napese', methods=['GET', 'POST'])
@login_required
def formulario_napese():
    form = NapeseForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                conn = conectar_bd()
                cur = conn.cursor()
                
                # Pega todos os campos do formulário
                dados = {
                    'email': current_user.email,
                    'nome_completo': request.form['nome_completo'],
                    'cpf': request.form['cpf'],
                    'cep': request.form['cep'],
                    'telefones': request.form['telefones'],
                    'data_nascimento': request.form['data_nascimento'],
                    'cidade': request.form['cidade'],
                    'estado': request.form['estado'],
                    'genero': request.form['genero'],
                    'profissao': request.form['profissao'],
                    'preferencia_atendimento': request.form['preferencia_atendimento'],
                    'renda_familiar': request.form['renda_familiar'],
                    'num_dependentes': request.form['num_dependentes'],
                    'sintomas_relevantes': request.form['sintomas_relevantes'],
                    'medicacoes': request.form['medicacoes'],
                    'substancias_psicoativas': request.form['substancias_psicoativas'],
                    'historico_acidentes': request.form['historico_acidentes'],
                    'historico_cirurgias': request.form['historico_cirurgias'],
                    'dores': request.form['dores'],
                    'acompanhamento_psiquiatrico': request.form['acompanhamento_psiquiatrico'],
                    'acompanhamento_psicologico': request.form['acompanhamento_psicologico'],
                    'tecnicas_corporais': request.form['tecnicas_corporais'],
                    'conhece_se': request.form['conhece_se'],
                    'motivo_procura': request.form['motivo_procura'],
                    'vivenciou_trauma': request.form['vivenciou_trauma'],
                    'descricao_evento': request.form['descricao_evento'],
                    'tempo_decorrido': request.form['tempo_decorrido'],
                    'envolveu_violencia': request.form['envolveu_violencia'],
                    'impacto_lembracas': request.form['impacto_lembracas'],
                    'impacto_evitacao': request.form['impacto_evitacao'],
                    'impacto_crencas': request.form['impacto_crencas'],
                    'impacto_apreensao': request.form['impacto_apreensao'],
                }

                # Adicionando campos condicionais
                if 'conheceu_site_trauma' in request.form and request.form['conheceu_site_trauma'].strip():
                    dados['conheceu_site_trauma'] = request.form['conheceu_site_trauma']

                if 'conheceu_instagram' in request.form and request.form['conheceu_instagram'].strip():
                    dados['conheceu_instagram'] = request.form['conheceu_instagram']

                if 'conheceu_indicacao' in request.form and request.form['conheceu_indicacao'].strip():
                    dados['conheceu_indicacao'] = request.form['conheceu_indicacao']

                if 'conheceu_treinamentos' in request.form and request.form['conheceu_treinamentos'].strip():
                    dados['conheceu_treinamentos'] = request.form['conheceu_treinamentos']

                if 'conheceu_google' in request.form and request.form['conheceu_google'].strip():
                    dados['conheceu_google'] = request.form['conheceu_google']

                if 'conheceu_rede_social' in request.form and request.form['conheceu_rede_social'].strip():
                    dados['conheceu_rede_social'] = request.form['conheceu_rede_social']

                if 'conheceu_psicologo' in request.form and request.form['conheceu_psicologo'].strip():
                    dados['conheceu_psicologo'] = request.form['conheceu_psicologo']

                if 'conheceu_outro' in request.form and request.form['conheceu_outro'].strip():
                    dados['conheceu_outro'] = request.form['conheceu_outro']

                if 'vivencia_direta' in request.form and request.form['vivencia_direta'].strip():
                    dados['vivencia_direta'] = request.form['vivencia_direta']

                if 'vivencia_testemunha' in request.form and request.form['vivencia_testemunha'].strip():
                    dados['vivencia_testemunha'] = request.form['vivencia_testemunha']

                if 'vivencia_familiar_amigo' in request.form and request.form['vivencia_familiar_amigo'].strip():
                    dados['vivencia_familiar_amigo'] = request.form['vivencia_familiar_amigo']

                if 'vivencia_trabalho' in request.form and request.form['vivencia_trabalho'].strip():
                    dados['vivencia_trabalho'] = request.form['vivencia_trabalho']

                if 'vivencia_nenhuma' in request.form and request.form['vivencia_nenhuma'].strip():
                    dados['vivencia_nenhuma'] = request.form['vivencia_nenhuma']

                if 'vivencia_outro' in request.form and request.form['vivencia_outro'].strip():
                    dados['vivencia_outro'] = request.form['vivencia_outro']
                
                # Debug: mostrar dados recebidos
                print("Dados recebidos:", dados)
                
                # Monta a query de inserção dinamicamente
                campos = ', '.join(dados.keys())
                placeholders = ', '.join(['%s'] * len(dados))
                query = f"""
                    INSERT INTO formulario_napese ({campos})
                    VALUES ({placeholders})
                """
                
                cur.execute(query, list(dados.values()))
                conn.commit()
                
                flash('Cadastro realizado com sucesso! Agora você será redirecionado para o dashboard.', 'success')
                return redirect(url_for('dashboard'))
                
            except Exception as e:
                conn.rollback()
                print(f"Erro ao salvar formulário: {str(e)}")
                if('formulario_napese_cpf_key' in str(e)):
                    flash('Erro ao enviar formulário. CPF já cadastrado', 'error')
                else:
                    flash('Erro ao enviar formulário. Por favor, tente novamente.', 'error')
            finally:
                cur.close()
                conn.close()
                
    return render_template('formulario_napese.html', form=form)

def init_db():
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        # 1. Primeiro, criar os tipos ENUM
        cur.execute("""
            DO $$ 
            BEGIN
                -- Criar tipo_atendimento
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipo_atendimento') THEN
                    CREATE TYPE tipo_atendimento AS ENUM ('PRESENCIAL', 'ONLINE');
                END IF;

                -- Criar faixa_renda
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'faixa_renda') THEN
                    CREATE TYPE faixa_renda AS ENUM ('ATE_2_SALARIOS', '2_A_4_SALARIOS', '4_A_10_SALARIOS', 'ACIMA_10_SALARIOS');
                END IF;

                -- Criar faixa_dependentes
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'faixa_dependentes') THEN
                    CREATE TYPE faixa_dependentes AS ENUM ('NENHUM', '1_A_2', '3_A_4', 'MAIS_DE_4');
                END IF;

                -- Criar resposta_sim_nao
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resposta_sim_nao') THEN
                    CREATE TYPE resposta_sim_nao AS ENUM ('SIM', 'NAO', 'NAO_SEI');
                END IF;
            END $$;
        """)
        
        # 2. Criar tabela usuarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                senha VARCHAR(255) NOT NULL,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status BOOLEAN DEFAULT TRUE,
                tipo_usuario VARCHAR(50) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                ultimo_login TIMESTAMP
            )
        """)

        # 2. Criar tabela terapeutas_pacientes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS terapeutas_pacientes (
                id SERIAL PRIMARY KEY,
                terapeuta_id INTEGER NOT NULL,
                paciente_id INTEGER NOT NULL,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status BOOLEAN DEFAULT TRUE
            );
                    
            alter table terapeutas_pacientes 
            add constraint fk_terapeura_id
            foreign key (terapeuta_id) 
            REFERENCES usuarios (id);
                    
            alter table terapeutas_pacientes 
            add constraint fk_paciente_id
            foreign key (paciente_id) 
            REFERENCES usuarios (id);
        """)

        # 3. Criar tabela formulario_napese
        cur.execute("""
            CREATE TABLE IF NOT EXISTS formulario_napese (
                id SERIAL PRIMARY KEY,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email VARCHAR(255) NOT NULL,
                nome_completo VARCHAR(255) NOT NULL,
                cpf VARCHAR(14) NOT NULL UNIQUE,
                cep VARCHAR(9) NOT NULL,
                telefones VARCHAR(100) NOT NULL,
                cidade VARCHAR(100) NOT NULL,
                estado VARCHAR(2) NOT NULL,
                preferencia_atendimento tipo_atendimento NOT NULL,
                renda_familiar faixa_renda NOT NULL,
                num_dependentes faixa_dependentes NOT NULL,
                data_nascimento DATE NOT NULL,
                genero VARCHAR(50) NOT NULL,
                profissao VARCHAR(100) NOT NULL,
                conheceu_site_trauma BOOLEAN DEFAULT FALSE,
                conheceu_instagram BOOLEAN DEFAULT FALSE,
                conheceu_indicacao BOOLEAN DEFAULT FALSE,
                conheceu_treinamentos BOOLEAN DEFAULT FALSE,
                conheceu_google BOOLEAN DEFAULT FALSE,
                conheceu_rede_social BOOLEAN DEFAULT FALSE,
                conheceu_psicologo BOOLEAN DEFAULT FALSE,
                conheceu_outro VARCHAR(255),
                sintomas_relevantes TEXT NOT NULL,
                medicacoes TEXT,
                substancias_psicoativas TEXT,
                historico_acidentes TEXT,
                historico_cirurgias TEXT,
                dores TEXT,
                acompanhamento_psiquiatrico resposta_sim_nao NOT NULL,
                acompanhamento_psicologico resposta_sim_nao NOT NULL,
                tecnicas_corporais TEXT,
                conhece_se BOOLEAN NOT NULL,
                motivo_procura TEXT NOT NULL,
                vivenciou_trauma BOOLEAN NOT NULL,
                descricao_evento TEXT,
                tempo_decorrido VARCHAR(100),
                envolveu_violencia BOOLEAN,
                vivencia_direta BOOLEAN DEFAULT FALSE,
                vivencia_testemunha BOOLEAN DEFAULT FALSE,
                vivencia_familiar_amigo BOOLEAN DEFAULT FALSE,
                vivencia_trabalho BOOLEAN DEFAULT FALSE,
                vivencia_nenhuma BOOLEAN DEFAULT FALSE,
                vivencia_outro TEXT,
                impacto_lembracas INTEGER CHECK (impacto_lembracas BETWEEN 0 AND 4),
                impacto_evitacao INTEGER CHECK (impacto_evitacao BETWEEN 0 AND 4),
                impacto_crencas INTEGER CHECK (impacto_crencas BETWEEN 0 AND 4),
                impacto_apreensao INTEGER CHECK (impacto_apreensao BETWEEN 0 AND 4),
                CONSTRAINT email_valido CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
                CONSTRAINT fk_email FOREIGN KEY (email) REFERENCES usuarios(email)
            )
        """)

        # 4. Criar índices
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_formulario_email ON formulario_napese(email);
            CREATE INDEX IF NOT EXISTS idx_formulario_cpf ON formulario_napese(cpf);
            CREATE INDEX IF NOT EXISTS idx_formulario_data_cadastro ON formulario_napese(data_cadastro);
        """)

        # Criar tabela terapeuta_napese
        cur.execute("""
            CREATE TABLE IF NOT EXISTS terapeuta_napese (
                id SERIAL PRIMARY KEY,
                nome_completo VARCHAR(255) NOT NULL,
                endereco_consultorio TEXT NOT NULL,
                cidade VARCHAR(100) NOT NULL,
                estado VARCHAR(2) NOT NULL,
                telefone VARCHAR(20) NOT NULL,
                celular VARCHAR(20) NOT NULL,
                email VARCHAR(255) NOT NULL REFERENCES usuarios(email),
                cpf VARCHAR(11) NOT NULL UNIQUE,
                nivel_atual VARCHAR(50) NOT NULL,
                ano_conclusao_avancado2 INTEGER,
                ano_conclusao_sep INTEGER,
                professores_formacao TEXT NOT NULL,
                formacao_academica TEXT NOT NULL,
                participa_grupo_estudo BOOLEAN NOT NULL,
                numero_supervisoes_ultimo_ano INTEGER NOT NULL,
                modalidade VARCHAR(50) NOT NULL,
                faixa_valor_sessao VARCHAR(50) NOT NULL,
                consultorio_acessivel BOOLEAN NOT NULL,
                observacao_acessibilidade TEXT,
                interesse_producao_cientifica BOOLEAN NOT NULL,
                associado_abt BOOLEAN NOT NULL,
                carta_recomendacao_path TEXT,
                sugestoes TEXT,
                concordou_termos BOOLEAN NOT NULL,
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'pendente'
            )
        """)

        conn.commit()
        print("Banco de dados inicializado com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar tabelas: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

class LoginForm(FlaskForm):
    pass  # Não precisamos definir campos aqui se estamos usando HTML puro

class TerapeutaForm(FlaskForm):
    pass  # Não precisamos definir campos aqui se estamos usando HTML puro

# Adicione também uma rota para o dashboard do terapeuta
@app.route('/dashboard-terapeuta')
@login_required
def dashboard_terapeuta():
    if not current_user.is_admin:
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('login'))
    return "Bem-vindo ao Dashboard do Terapeuta!"

# Atualizar a rota existente ou criar se não existir
@app.route('/cadastro-paciente')
def cadastro_paciente():
    return render_template('cadastro_paciente.html')

@app.route('/cadastro-usuario-terapeuta', methods=['GET', 'POST'])
def cadastro_usuario_terapeuta():
    form = TerapeutaForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                if request.form.get('email') and request.form.get('senha'):
                    email = request.form.get('email')
                    tipo_usuario = 'terapeuta'
                    password = request.form.get('senha')

                    # Gera o hash da senha
                    hashed_password = generate_password_hash(password)

                    conn = conectar_bd()
                    cur = conn.cursor()
                        
                    try:
                        # Insere o novo usuário no banco de dados
                        cur.execute("""
                        INSERT INTO usuarios (email, tipo_usuario, senha, status)
                        VALUES (%s, %s, %s, true)
                        """, (email, tipo_usuario, hashed_password))
                        conn.commit()
                            
                        flash('Novo usuário criado com sucesso!', 'success')
                    except Exception as e:
                        print(f"Erro ao criar usuário: {e}")
                        flash('Erro ao criar usuário.', 'error')
                    finally:
                        cur.close()
                        conn.close()

                    return redirect(url_for('login_terapeuta'))
                
            except Exception as e:
                print(f"Erro ao cadastrar terapeuta: {str(e)}")
                if 'conn' in locals():
                    conn.rollback()
                flash('Erro ao realizar cadastro. Por favor, tente novamente.', 'error')
            finally:
                if 'cur' in locals():
                    cur.close()
                if 'conn' in locals():
                    conn.close()
    
    return render_template('cadastro_terapeuta.html', form=form)

# Rotas do Admin
@app.route('/admin/base')
@admin_required
def admin_base():
    return render_template('base.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin-usuarios')
@login_required
def admin_usuarios():
    if not current_user.is_admin():  # Verifica se o usuário é um administrador
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 5  # Número de usuários por página
    offset = (page - 1) * per_page

    conn = conectar_bd()
    cur = conn.cursor()
    
    try:
        # Recupera a contagem total de usuários
        cur.execute("SELECT COUNT(*) FROM usuarios where status = true")
        total_usuarios = cur.fetchone()[0]

        # Recupera os usuários para a página atual
        cur.execute("SELECT id, email, tipo_usuario FROM usuarios where status = true order by id LIMIT %s OFFSET %s", (per_page, offset))
        usuarios = cur.fetchall()

        # Formata os dados
        usuarios_formatados = [
            {'id': usuario[0], 'email': usuario[1], 'tipo_usuario': usuario[2]}
            for usuario in usuarios
        ]

        # Configuração da paginação
        has_prev = page > 1
        has_next = offset + per_page < total_usuarios
        total_pages = ceil(total_usuarios / per_page)

        paginacao = {
            'items': usuarios_formatados,
            'has_prev': has_prev,
            'has_next': has_next,
            'page': page,
            'pages': total_pages,
            'prev_num': page - 1,
            'next_num': page + 1,
        }

    except Exception as e:
        print(f"Erro ao buscar usuários: {e}")
        flash('Erro ao carregar usuários.', 'error')
        paginacao = {
            'items': [],
            'has_prev': False,
            'has_next': False,
            'page': 1,
            'pages': 1,
        }
    finally:
        cur.close()
        conn.close()

    return render_template('admin/usuarios.html', usuarios=paginacao, form=FlaskForm())

@app.route('/editar-usuario', methods=['POST'])
@login_required
def editar_usuario():
    if not current_user.is_admin():
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('dashboard'))

    user_id = request.form['user_id']
    email = request.form['email']
    password = request.form['password']

    # Verifica se a senha foi fornecida
    if password:
        # Gera o hash da senha
        hashed_password = generate_password_hash(password)
    else:
        hashed_password = None  # Caso não tenha nova senha, não faz alteração
    
    # Lógica para atualizar o usuário no banco de dados
    try:
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET email = %s, senha = %s WHERE id = %s", (email, hashed_password, user_id))
        conn.commit()
        flash('Usuário atualizado com sucesso!', 'success')
    except Exception as e:
        flash('Erro ao atualizar o usuário.', 'error')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('admin_usuarios'))

@app.route('/remover-usuario/<int:user_id>', methods=['POST'])
@login_required
def remover_usuario(user_id):
    form = FlaskForm()

    if not current_user.is_admin():
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('dashboard'))

    conn = conectar_bd()
    cur = conn.cursor()

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Remover o usuário do banco de dados
                cur.execute("UPDATE usuarios SET status=false WHERE id = %s", (user_id,))
                conn.commit()  # Confirma a exclusão no banco

                flash('Usuário removido com sucesso!', 'success')
            except Exception as e:
                print(f"Erro ao remover o usuário: {e}")
                flash('Erro ao remover o usuário.', 'error')
            finally:
                cur.close()
                conn.close()

    return redirect(url_for('admin_usuarios'))  # Redireciona para a lista de usuários

@app.route('/criar-usuario', methods=['POST'])
@login_required
def criar_usuario():
    if not current_user.is_admin():
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('dashboard'))

    email = request.form.get('email')
    tipo_usuario = request.form.get('tipo_usuario')
    password = request.form.get('password')

    # Gera o hash da senha
    hashed_password = generate_password_hash(password)

    conn = conectar_bd()
    cur = conn.cursor()
    
    try:
        # Insere o novo usuário no banco de dados
        cur.execute("""
            INSERT INTO usuarios (email, tipo_usuario, senha, status)
            VALUES (%s, %s, %s, true)
        """, (email, tipo_usuario, hashed_password))
        conn.commit()
        
        flash('Novo usuário criado com sucesso!', 'success')
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        flash('Erro ao criar usuário.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin_usuarios'))

@app.route('/get_pacientes/<int:terapeuta_id>')
@login_required
def get_pacientes(terapeuta_id):
    if not current_user.is_authenticated or not current_user.is_admin():  # Verifica se o usuário está autenticado e é admin
        return jsonify({'error': 'Acesso não autorizado'}), 403

    conn = conectar_bd()
    cur = conn.cursor()

    try:
        # Busca os pacientes vinculados ao terapeuta
        cur.execute("""
            select usu_paciente.id, usu_paciente.email from terapeutas_pacientes tp
            inner join usuarios usu_terapeuta on (usu_terapeuta.id = terapeuta_id)
            inner join usuarios usu_paciente on (usu_paciente.id = paciente_id)
            WHERE tp.terapeuta_id = %s and tp.status = true 
        """, (terapeuta_id,))
        
        pacientes = cur.fetchall()

        # Formata os dados
        pacientes_formatados = [
            {'id': paciente[0], 'email': paciente[1]} 
            for paciente in pacientes
        ]

        print(pacientes_formatados)
        return jsonify(pacientes_formatados)

    except Exception as e:
        print(f"Erro ao buscar pacientes vinculados: {e}")
        return jsonify({'error': 'Erro ao buscar pacientes vinculados'}), 500

    finally:
        cur.close()
        conn.close()

@app.route('/pacientes_disponiveis', methods=['GET'])
@login_required
def pacientes_disponiveis():
    if not current_user.is_authenticated or not current_user.is_admin():  # Verifica se o usuário está autenticado e é admin
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('admin_usuarios'))

    conn = conectar_bd()
    cur = conn.cursor()

    try:
        # Obter IDs dos pacientes já vinculados
        cur.execute("""
            SELECT paciente_id FROM terapeutas_pacientes 
            WHERE status = true
        """)
        vinculados = [row[0] for row in cur.fetchall()]

        # Obter lista de pacientes disponíveis
        if vinculados:
            query = """
                SELECT id, email FROM usuarios 
                WHERE tipo_usuario = 'paciente' AND id NOT IN %s
            """
            cur.execute(query, (tuple(vinculados),))
        else:
            query = """
                SELECT id, email FROM usuarios 
                WHERE tipo_usuario = 'paciente'
            """
            cur.execute(query)

        pacientes = cur.fetchall()
        return jsonify([{'id': paciente[0], 'email': paciente[1]} for paciente in pacientes])

    except Exception as e:
        print(f"Erro ao buscar pacientes disponíveis: {e}")
        flash( 'Erro ao buscar pacientes disponíveis!', 'error')
        return redirect(url_for('admin_usuarios'))

    finally:
        cur.close()
        conn.close()

@app.route('/vincular_paciente', methods=['POST'])
@login_required
def vincular_paciente():
    if not current_user.is_authenticated or not current_user.is_admin():  # Verifica se o usuário está autenticado e é admin
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('admin_usuarios'))

    terapeuta_id = request.form.get('terapeuta_id')
    paciente_email = request.form.get('novo_paciente')

    if not terapeuta_id or not paciente_email:
        flash('Dados incompletos!', 'error')
        return redirect(url_for('admin_usuarios'))

    conn = conectar_bd()
    cur = conn.cursor()

    try:
        # Verificar se o paciente existe
        cur.execute("SELECT id FROM usuarios WHERE email = %s", (paciente_email,))
        paciente = cur.fetchone()
        if not paciente:
            flash('Paciente não encontrado!', 'error')
            return redirect(url_for('admin_usuarios'))

        paciente_id = paciente[0]

        # Verificar se já existe um vínculo ativo
        cur.execute("""
            SELECT 1 FROM terapeutas_pacientes 
            WHERE terapeuta_id = %s AND paciente_id = %s AND status = true
        """, (terapeuta_id, paciente_id))
        if cur.fetchone():
            flash('Paciente já está vinculado!', 'error')
            return redirect(url_for('admin_usuarios'))

        # Verificar se já existe um vínculo inativo
        cur.execute("""
            SELECT id FROM terapeutas_pacientes 
            WHERE terapeuta_id = %s AND paciente_id = %s AND status = false
        """, (terapeuta_id, paciente_id))
        vinculo_inativo = cur.fetchone()

        if vinculo_inativo:
            # Se o vínculo inativo existe, atualize o status para true
            cur.execute("""
                UPDATE terapeutas_pacientes 
                SET status = true 
                WHERE id = %s
            """, (vinculo_inativo[0],))
            conn.commit()
            flash('Paciente vinculado com sucesso!', 'success')
        else:
            # Caso contrário, cria um novo vínculo
            cur.execute("""
                INSERT INTO terapeutas_pacientes (terapeuta_id, paciente_id, status) 
                VALUES (%s, %s, true)
            """, (terapeuta_id, paciente_id))
            conn.commit()
            flash('Paciente vinculado com sucesso!', 'success')

        return redirect(url_for('admin_usuarios'))

    except Exception as e:
        print(f"Erro ao vincular paciente: {e}")
        flash('Erro ao vincular paciente!', 'error')
        return redirect(url_for('admin_usuarios'))

    finally:
        cur.close()
        conn.close()

@app.route('/remover_vinculo', methods=['POST'])
@login_required
def remover_vinculo():
    terapeuta_id = request.form.get('terapeuta_id')
    paciente_id = request.form.get('paciente_id')

    print(f"terapeuta_id: {terapeuta_id}, paciente_id: {paciente_id}")

    if not terapeuta_id or not paciente_id:
        flash('Parâmetros inválidos', 'error')
        return redirect(url_for('admin_usuarios'))

    conn = conectar_bd()
    cur = conn.cursor()

    try:
        # Verificar se o terapeuta e paciente estão vinculados
        cur.execute(
            "SELECT 1 FROM terapeutas_pacientes WHERE terapeuta_id = %s AND paciente_id = %s",
            (terapeuta_id, paciente_id)
        )
        if not cur.fetchone():
            flash('Vínculo não encontrado', 'error')
            return redirect(url_for('admin_usuarios'))

        # Remover o vínculo
        cur.execute(
            "UPDATE terapeutas_pacientes SET status=false WHERE terapeuta_id = %s AND paciente_id = %s",
            (terapeuta_id, paciente_id)
        )
        conn.commit()

        flash('Vínculo removido com sucesso', 'success')
        return redirect(url_for('admin_usuarios'))

    except Exception as e:
        print(f"Erro ao remover vínculo: {e}")
        conn.rollback()
        flash('Erro ao remover vínculo', 'error')
        return redirect(url_for('admin_usuarios'))

    finally:
        cur.close()
        conn.close()

@app.route('/gerar_pdf/<user_email>')
@login_required
def gerar_pdf(user_email):
    # Verificar se o usuário tem permissão para acessar
    if not current_user.is_authenticated or not current_user.is_admin():
        flash('Acesso não autorizado!', 'error')
        return redirect(url_for('admin_usuarios'))

    conn = conectar_bd()
    cur = conn.cursor()

    try:
        # Consulta as informações do usuário pelo email
        cur.execute("""
            SELECT *
            FROM formulario_napese 
            WHERE email = %s
        """, (user_email,))
        paciente = cur.fetchone()

        if not paciente:
            flash('Dados do paciente não encontrados!', 'error')
            return redirect(url_for('admin_usuarios'))

        # Nome das colunas da tabela
        colunas = [
            "ID", "Data de Cadastro", "Email", "Nome Completo", "CPF", "CEP", "Telefones", "Cidade", "Estado",
            "Preferência de Atendimento", "Renda Familiar", "Número de Dependentes", "Data de Nascimento", "Gênero",
            "Profissão", "Conheceu pelo Site/Trauma", "Conheceu pelo Instagram", "Conheceu por Indicação",
            "Conheceu pelos Treinamentos", "Conheceu pelo Google", "Conheceu por Redes Sociais", "Conheceu por Psicólogo",
            "Conheceu por Outro Meio", "Sintomas Relevantes", "Medicações", "Substâncias Psicoativas", "Histórico de Acidentes",
            "Histórico de Cirurgias", "Dores", "Acompanhamento Psiquiátrico", "Acompanhamento Psicológico", "Técnicas Corporais",
            "Se Conhece", "Motivo da Procura", "Vivenciou Trauma", "Descrição do Evento", "Tempo Decorrido", "Envolveu Violência",
            "Vivência Direta", "Vivência como Testemunha", "Vivência de Familiar ou Amigo", "Vivência no Trabalho",
            "Sem Vivência", "Outra Vivência", "Impacto das Lembranças", "Impacto da Evitação", "Impacto nas Crenças",
            "Impacto na Apreensão"
        ]

        # Ajustar dados do paciente
        paciente_formatado = []
        for coluna, valor in zip(colunas, paciente):
            if isinstance(valor, bool):
                valor = "Sim" if valor else "Não"
            elif isinstance(valor, (datetime.date, datetime.datetime)):
                valor = valor.strftime("%d/%m/%Y")
            paciente_formatado.append((coluna, valor))

        # Criar o PDF em memória
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)

        # Título do PDF
        c.setFont("Helvetica-Bold", 16)

        # Definir a cor laranja para o fundo
        c.setFillColorRGB(1, 0.647, 0)  # Cor laranja (RGB)

        # Desenhar o retângulo com fundo laranja
        c.rect(45, 750, 500, 40, stroke=0, fill=1)  # Ajustado para y=750

        # Definir a cor do texto (branco)
        c.setFillColorRGB(1, 1, 1)  # Cor branca

        # Adicionar o texto centralizado no retângulo
        c.drawCentredString(295, 770, "Relatório do Paciente")  # Ajuste da posição y para 770

        # Estilização e início das informações
        c.setFont("Helvetica-Bold", 12)
        c.setFillColorRGB(0, 0, 0)  # Cor preta
        y = 720  # Ajuste a posição inicial de y para que não sobreponha o título
        for coluna, valor in paciente_formatado:
            # Verificar se a posição y ultrapassa a margem inferior da página
            if y < 50:  # Quebra de página
                c.showPage()
                c.setFont("Helvetica-Bold", 12)
                y = 770  # Ajustar a posição no início da nova página

            # Desenhar borda ao redor da pergunta e resposta
            c.rect(45, y - 15, 500, 20, stroke=1, fill=0)

            # Ajustar a posição do texto para ficar acima da borda
            c.drawString(50, y - 10, f"{coluna}:")  # Ajustado para 5 pixels abaixo da borda
            c.setFont("Helvetica", 12)
            c.drawString(250, y - 10, str(valor))  # Ajustado para 5 pixels abaixo da borda
            y -= 30  # Ajuste de espaçamento para a próxima linha

        # Finalizar o PDF
        c.save()
        buffer.seek(0)


        # Retornar o PDF como resposta
        return Response(
            buffer,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment;filename=relatorio_paciente.pdf'}
        )

    except Exception as e:
        print(f"Erro ao gerar PDF: {e}")
        flash('Erro ao gerar PDF!', 'error')
        return redirect(url_for('admin_usuarios'))

    finally:
        cur.close()
        conn.close()

# Rotas do Terapeuta
@app.route('/terapeuta/dashboard')
@terapeuta_required
def terapeuta_dashboard():
    return render_template('terapeuta/dashboard.html')

@app.route('/terapeuta/meus-pacientes')
@terapeuta_required
def terapeuta_pacientes():
    return render_template('terapeuta/pacientes.html')

# Rotas do Paciente (não precisam de decorator especial, apenas login_required)
@app.route('/paciente/perfil')
@login_required
def paciente_perfil():
    return render_template('paciente/perfil.html')

def criar_usuarios_teste():
    conn = conectar_bd()
    cur = conn.cursor()
    try:
        # Criar admin
        cur.execute("""
            INSERT INTO usuarios (email, senha, tipo_usuario, status)
            VALUES (%s, %s, 'admin', true)
            ON CONFLICT (email) DO NOTHING
        """, ('admin@teste.com', generate_password_hash('admin123')))

        # Criar terapeuta
        cur.execute("""
            INSERT INTO usuarios (email, senha, tipo_usuario, status)
            VALUES (%s, %s, 'terapeuta', true)
            ON CONFLICT (email) DO NOTHING
        """, ('terapeuta@teste.com', generate_password_hash('terapeuta123')))

        # Criar paciente
        cur.execute("""
            INSERT INTO usuarios (email, senha, tipo_usuario, status)
            VALUES (%s, %s, 'paciente', true)
            ON CONFLICT (email) DO NOTHING
        """, ('paciente@teste.com', generate_password_hash('paciente123')))

        conn.commit()
        print("Usuários de teste criados com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar usuários: {str(e)}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# Configurações para upload de arquivos
UPLOAD_FOLDER = 'uploads/cartas_recomendacao'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/formulario-terapeuta', methods=['GET', 'POST'])
@login_required
def formulario_terapeuta():
    form = FlaskForm()
    
    # Adicione este print para debug
    print("Method:", request.method)
    if request.method == 'POST':
        print("Form data:", request.form)  # Debug dos dados do formulário
        print("Files:", request.files)     # Debug dos arquivos
        
        try:
            # Verifica se já existe um formulário preenchido
            conn = conectar_bd()
            cur = conn.cursor()
            
            print(f"Verificando formulário existente para email: {current_user.email}") # Debug log
            cur.execute("""
                SELECT id FROM terapeuta_napese 
                WHERE email = %s
            """, (current_user.email,))
            
            if cur.fetchone():
                flash('Você já preencheu o formulário anteriormente.', 'info')
                return redirect(url_for('dashboard_terapeuta'))
            
            # Processar upload da carta de recomendação
            carta_path = None
            if 'carta_recomendacao' in request.files:
                arquivo = request.files['carta_recomendacao']
                if arquivo and arquivo.filename and allowed_file(arquivo.filename):
                    filename = secure_filename(f"{current_user.email}_{arquivo.filename}")
                    if not os.path.exists(UPLOAD_FOLDER):
                        os.makedirs(UPLOAD_FOLDER)
                    arquivo.save(os.path.join(UPLOAD_FOLDER, filename))
                    carta_path = filename

            # Coletar dados do formulário
            dados = {
                'nome_completo': request.form['nome_completo'],
                'endereco_consultorio': request.form['endereco_consultorio'],
                'cidade': request.form['cidade'],
                'estado': request.form['estado'],
                'telefone': request.form['telefone'],
                'celular': request.form['celular'],
                'email': current_user.email,
                'cpf': request.form['cpf'].replace('.', '').replace('-', ''),
                'nivel_atual': request.form['nivel_atual'],

                # descomentar após adicionar os campos no html
                # 'ano_conclusao_avancado2': request.form.get('ano_conclusao_avancado2') or None,
                # 'ano_conclusao_sep': request.form.get('ano_conclusao_sep') or None,
                # 'professores_formacao': request.form['professores_formacao'],
                # 'formacao_academica': request.form['formacao_academica'],
                # 'participa_grupo_estudo': 'participa_grupo_estudo' in request.form,
                # 'numero_supervisoes_ultimo_ano': int(request.form.get('numero_supervisoes', 0)),
                # 'modalidade': request.form['modalidade'],
                # 'faixa_valor_sessao': request.form['faixa_valor_sessao'],
                # 'consultorio_acessivel': 'consultorio_acessivel' in request.form,
                # 'observacao_acessibilidade': request.form.get('observacao_acessibilidade', ''),
                # 'interesse_producao_cientifica': 'interesse_producao_cientifica' in request.form,
                # 'associado_abt': 'associado_abt' in request.form,
                # 'carta_recomendacao_path': carta_path,
                # 'sugestoes': request.form.get('sugestoes', ''),
                # 'concordou_termos': 'concordou_termos' in request.form

                # apagar após adicionar os campos no html
                'ano_conclusao_avancado2': request.form.get('ano_conclusao_avancado2') or None,
                'ano_conclusao_sep': request.form.get('ano_conclusao_sep') or None,
                'professores_formacao': 'teste',
                'formacao_academica': 'teste',
                'participa_grupo_estudo': True,
                'numero_supervisoes_ultimo_ano': 1,
                'modalidade': 'teste',
                'faixa_valor_sessao': 'teste',
                'consultorio_acessivel': True,
                'interesse_producao_cientifica': True,
                'associado_abt': True,
                'carta_recomendacao_path': carta_path,
                'concordou_termos': True
            }

            print("Dados coletados:", dados) # Debug log

            # Construir query de inserção
            campos = ', '.join(dados.keys())
            placeholders = ', '.join(['%s'] * len(dados))
            
            query = f"""
                INSERT INTO terapeuta_napese ({campos})
                VALUES ({placeholders})
                RETURNING id
            """
            print("Query SQL:", query) # Debug log
            print("Valores:", list(dados.values())) # Debug log

            cur.execute(query, list(dados.values()))
            
            conn.commit()
            print("Dados inseridos com sucesso!") # Debug log
            
            flash('Formulário enviado com sucesso! Aguarde a aprovação do administrador.', 'success')
            return redirect(url_for('dashboard_terapeuta'))
                
        except Exception as e:
            print(f"Erro detalhado: {str(e)}")  # Log mais detalhado do erro
            if conn:
                conn.rollback()
            flash('Erro ao enviar formulário. Por favor, tente novamente.', 'error')
            
        finally:
            if conn:
                cur.close()
                conn.close()
    
    return render_template('formulario_terapeuta.html', form=form)

@app.before_request
def log_request_info():
    print('Headers: %s', request.headers)
    print('Body: %s', request.get_data())

# Adicione no final do arquivo
if __name__ == '__main__':
    init_db()
    criar_usuarios_teste()
    app.run(debug=True)