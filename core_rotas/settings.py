import os
from pathlib import Path
import dj_database_url

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SEGURANÇA ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-sua-chave-secreta-aqui')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [
    'web-production-1bc34.up.railway.app', 
    '.railway.app', 
    '127.0.0.1', 
    'localhost'
]

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
    'logistica',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
        'DIRS': [],
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

# ==============================================================================
# CONFIGURAÇÃO DE BASE DE DADOS (FORÇAR NUVEM EM PRODUÇÃO)
# ==============================================================================

DATABASE_URL = os.environ.get('DATABASE_URL')

# Se estamos na nuvem (DEBUG = False), EXIGIMOS o PostgreSQL da Railway
if not DEBUG:
    if not DATABASE_URL:
        raise ValueError("ERRO GRAVE: DATABASE_URL não foi encontrada na Railway!")
    
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    # Se estamos no seu PC (DEBUG = True), usamos o ficheiro SQLite local
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# --- FICHEIROS ESTÁTICOS ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CONFIGURAÇÕES DE ACESSO ---
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = True