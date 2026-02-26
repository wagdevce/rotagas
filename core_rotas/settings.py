import os
from pathlib import Path
import dj_database_url

# Caminho base do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# SEGURANÇA E AMBIENTE
# ==============================================================================
# SECRET_KEY: Usa a da nuvem ou uma padrão para o seu PC
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-chave-secreta-padrao-local')

# DEBUG: Fica True no seu PC e False na Nuvem (se você definir a variável lá)
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ALLOWED_HOSTS: Aceita o seu PC, rede local e o domínio da Railway
ALLOWED_HOSTS = ['*']

# CSRF: Essencial para formulários de Login funcionarem na Railway sem dar Erro 403
CSRF_TRUSTED_ORIGINS = ['https://*.railway.app']

# ==============================================================================
# APLICAÇÕES INSTALADAS
# ==============================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # A nossa aplicação principal
    'logistica',
]

# ==============================================================================
# MIDDLEWARES (O "Filtro" de cada requisição)
# ==============================================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <--- WhiteNoise gere o CSS na nuvem
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
# BASE DE DADOS (LÓGICA HÍBRIDA)
# ==============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Se encontrou a URL (Railway), liga-se ao PostgreSQL profissional
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Se não encontrou (Seu PC), usa o ficheiro SQLite local
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ==============================================================================
# VALIDAÇÃO DE SENHAS
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# ==============================================================================
# INTERNACIONALIZAÇÃO (Idioma e Fuso Horário)
# ==============================================================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza' # Ajustado para o seu fuso horário
USE_I18N = True
USE_TZ = True

# ==============================================================================
# FICHEIROS ESTÁTICOS (CSS, JS, Imagens)
# ==============================================================================
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Versão tolerante do WhiteNoise: Se faltar um ícone minúsculo, não deita o site abaixo
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# REDIRECIONAMENTOS DE LOGIN
# ==============================================================================
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'