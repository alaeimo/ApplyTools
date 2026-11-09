from pathlib import Path
import environ
import os
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
env_path = Path(".env")
environ.Env.read_env(BASE_DIR/env_path)

DEBUG = env.bool('DEBUG')
ENABLE_DJANGO_ADMIN_PANEL = env.bool('ENABLE_DJANGO_ADMIN_PANEL')
SECRET_KEY = env('SECRET_KEY')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOWED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')
CORS_ALLOW_ALL_ORIGINS = DEBUG

# ─── AI Provider settings ─────────────────────────────────────
# Switch provider: 'gemini' (Google AI Studio, free tier, 1M context)
# or 'deepseek' (paid, 128K context). Default: 'gemini'.
APPLYTOOLS_AI_PROVIDER = os.environ.get('APPLYTOOLS_AI_PROVIDER', 'gemini').lower().strip()

# ─── Gemini (Google AI Studio) settings ───────────────────────
# Get a free key at https://aistudio.google.com/apikey
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', os.environ.get('GOOGLE_API_KEY', ''))
# Default model: Gemini 2.0 Flash (fast, 1M context, free-tier eligible)
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')
GEMINI_TEMPERATURE = float(os.environ.get('GEMINI_TEMPERATURE', '0.7') or '0.7')
GEMINI_MAX_OUTPUT_TOKENS = int(os.environ.get('GEMINI_MAX_OUTPUT_TOKENS', '8192') or '8192')
GEMINI_TIMEOUT = int(os.environ.get('GEMINI_TIMEOUT', '120') or '120')

# Retry configuration for transient network errors
GEMINI_MAX_RETRIES = int(os.environ.get('GEMINI_MAX_RETRIES', '3') or '3')
GEMINI_RETRY_BASE_DELAY = float(os.environ.get('GEMINI_RETRY_BASE_DELAY', '2.0') or '2.0')

# ─── Matcher tuning (shared by both providers) ────────────────
# Delay (seconds) between match calls — protects against rate limits.
DEEPSEEK_INTER_CALL_DELAY = float(os.environ.get('DEEPSEEK_INTER_CALL_DELAY', '0') or '0')
# Rotate conversation every N positions to avoid context overflow.
# Kept the legacy name so views.py and matcher.py don't need changes.
DEEPSEEK_ROTATE_EVERY = float(os.environ.get('DEEPSEEK_ROTATE_EVERY', '15') or '15')

AI_FALLBACK_MODELS = os.environ.get('AI_FALLBACK_MODELS', '')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'django_filters',
    'rest_framework', 
    'rest_framework_simplejwt.token_blacklist',
    'djoser',
    'apps.cvs',
    'apps.scraper',
    'apps.ai',
    'apps.api',
    'apps.extension',
    'apps.websites',
    'apps.positions',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
MEDIA_HOST = env('MEDIA_HOST')
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}


REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'apps.extension.authentication.ExtensionTokenAuthentication',  
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO', 
    },
}