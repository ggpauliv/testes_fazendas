"""
Django settings for AgroTalhoes project.

Sistema de Gestão de Fazendas - Configurações principais
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carregar variáveis de ambiente do arquivo .env
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-development-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['191.252.178.97', 'hkfazendas.com', 'www.hkfazendas.com', 'localhost', '127.0.0.1', '*']

# CSRF Trusted Origins (Importante para evitar erro 403 em requisições POST)
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://hkfazendas.com',
    'https://www.hkfazendas.com',
    'http://191.252.178.97'
]

# ==============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS SQL SERVER
# ==============================================================================

# Lê configurações do .env ou usa valores padrão
DB_ENGINE = os.getenv('DB_ENGINE', 'mssql').lower()
DB_NAME = os.getenv('DB_NAME', 'db_talhoes')
# Para mssql o padrão era localhost\SQLEXPRESS, para pg geralmente é localhost
DEFAULT_HOST = r'localhost\SQLEXPRESS' if DB_ENGINE == 'mssql' else 'localhost'
DB_HOST = os.getenv('DB_HOST', DEFAULT_HOST)
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_PORT = os.getenv('DB_PORT', '5432' if DB_ENGINE == 'postgresql' else '')

if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }
else:
    # CONFIGURAÇÃO DO BANCO DE DADOS SQL SERVER (LEGACY)
    USE_TRUSTED_CONNECTION = os.getenv('USE_TRUSTED_CONNECTION', 'yes').lower() == 'yes'
    if USE_TRUSTED_CONNECTION:
        # Autenticação Windows (Trusted Connection)
        DATABASES = {
            'default': {
                'ENGINE': 'mssql',
                'NAME': DB_NAME,
                'HOST': DB_HOST,
                'PORT': DB_PORT,
                'OPTIONS': {
                    'driver': 'ODBC Driver 17 for SQL Server',
                    'extra_params': 'TrustServerCertificate=yes;Trusted_Connection=yes',
                    'charset': 'UTF-8',
                },
            }
        }
    else:
        # Autenticação SQL Server (usuário/senha)
        DATABASES = {
            'default': {
                'ENGINE': 'mssql',
                'NAME': DB_NAME,
                'HOST': DB_HOST,
                'PORT': DB_PORT,
                'USER': DB_USER,
                'PASSWORD': DB_PASSWORD,
                'OPTIONS': {
                    'driver': 'ODBC Driver 17 for SQL Server',
                    'extra_params': 'TrustServerCertificate=yes',
                    'charset': 'UTF-8',
                },
            }
        }

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
    
    # Apps de terceiros
    'crispy_forms',
    'crispy_bootstrap5',
    'django.contrib.humanize',
    
    # Apps do projeto
    'core',
]

# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'agrotalhoes.urls'

# ==============================================================================
# TEMPLATES
# ==============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.sistema_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'agrotalhoes.wsgi.application'

# ==============================================================================
# VALIDAÇÃO DE SENHA
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ==============================================================================
# INTERNACIONALIZAÇÃO
# ==============================================================================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
NUMBER_GROUPING = 3

# ==============================================================================
# ARQUIVOS ESTÁTICOS E MÍDIA
# ==============================================================================

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==============================================================================
# CONFIGURAÇÕES CRISPY FORMS (Bootstrap 5)
# ==============================================================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"



# ==============================================================================
# DEFAULT PRIMARY KEY
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# LOGIN/LOGOUT
# ==============================================================================

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

# ==============================================================================
# CACHE (Para Cotações e Mapas)
# ==============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
