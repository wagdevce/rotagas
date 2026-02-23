import os
from pathlib import Path
import dj_database_url

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SEGURANÇA ---
# Em produção (Railway), o ideal é usar uma variável de ambiente. 
# Se não houver, usa esta chave padrão.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-sua-chave-secreta-aqui')

# DEBUG: Falso em produção, Verdadeiro se não encontrar a variável (local)
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Domínios permitidos
ALLOWED_HOSTS = [
    'web-production-1bc34.up.railway.app', 
    '.railway.app', 
    '127.0.0.1', 
    'localhost'
]

# --- CORREÇÃO DO ERRO 403 FORBIDDEN ---
# Necessário para que o Django aceite formulários via HTTPS na Railway
CSRF_TRUSTED_ORIGINS = [
    'https://web-production-1bc34.up.railway.app'
]

# --- DEFINIÇÃO DAS APPS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # App do Sistema Rotagas
    'logistica',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Servidor de ficheiros estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core_rotas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [], # O Django busca automaticamente nas pastas 'templates' das apps
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core_rotas.wsgi.application'

# --- BANCO DE DADOS (HÍBRIDO) ---
# Se estiver na Railway, usa o Postgres. Se estiver local, usa o SQLite.
import dj_database_url

# Configuração robusta de banco de dados
DATABASES = {
    'default': dj_database_url.config(
        # Se não houver DATABASE_URL (local), usa SQLite
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# --- VALIDAÇÃO DE SENHAS ---
# Simplificado para o MVP. Em produção real, deve ser mais rigoroso.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 4}},
]

# --- INTERNACIONALIZAÇÃO ---
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True

# --- FICHEIROS ESTÁTICOS (WhiteNoise) ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Esta configuração garante que o CSS funcione mesmo se o servidor mudar de URL
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CONFIGURAÇÕES DE ACESSO ---
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

# Tipo padrão de ID para os modelos
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'