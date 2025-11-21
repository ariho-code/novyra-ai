"""
Django settings for novyra_ai project – Fully Vercel / Production Ready
"""

import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()  # Load .env in local development only

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# ========== SECURITY & ENVIRONMENT ==========
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required!")

DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Detect Vercel environment
VERCEL = os.getenv('VERCEL', '0') == '1'

# ALLOWED_HOSTS – safe & flexible
if DEBUG:
    ALLOWED_HOSTS = ['*']  # Only safe during local dev
elif VERCEL:
    ALLOWED_HOSTS = ['*']  # Vercel handles host validation via their proxy
else:
    allowed = os.getenv('ALLOWED_HOSTS', '')
    ALLOWED_HOSTS = [h.strip() for h in allowed.split(',') if h.strip()] or ['*']

# Embed widget base URL (used in embed script generation)
EMBED_BASE_URL = os.getenv('EMBED_BASE_URL')  # e.g., https://yourdomain.vercel.app

# ========== APPLICATION DEFINITION ==========
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'channels',

    # Local
    'chat_app',
]

# ========== MIDDLEWARE – WHITENOISE ADDED (CRITICAL FOR VERCEL) ==========
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # ← MUST be right after SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'chat_app.middleware.LoginTrackingMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'novyra_ai.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'novyra_ai.wsgi.application'
ASGI_APPLICATION = 'novyra_ai.asgi.application'

# ========== DATABASE ==========
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql' if os.getenv('DB_ENGINE') == 'postgresql' else 'django.db.backends.sqlite3',
        'NAME': os.getenv('DB_NAME', BASE_DIR / 'db.sqlite3'),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# ========== PASSWORD VALIDATION ==========
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========== INTERNATIONALIZATION ==========
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ========== STATIC & MEDIA FILES (Vercel-ready with WhiteNoise) ==========
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Django ≥4.2 style (optional but recommended)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========== DJANGO REST FRAMEWORK ==========
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ========== SIMPLE JWT ==========
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

# ========== CORS ==========
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', '')
    CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins.split(',') if o.strip()] if cors_origins else []
CORS_ALLOW_CREDENTIALS = True

# ========== CHANNELS (WebSockets) ==========
# Warning: RedisChannelLayer will NOT work on Vercel (serverless). 
# For production WebSockets on Vercel → use a separate service (e.g., Pusher, Ably, Socket.io on Railway/Render)
if DEBUG or VERCEL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [os.getenv('REDIS_URL', 'redis://127.0.0.1:6379')],
            },
        },
    }

# ========== AI & DEEPSEEK ==========
AI_CONFIDENCE_THRESHOLD = float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7'))
AI_ESCALATION_KEYWORDS = ['help', 'agent', 'human', 'support', 'escalate']

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_BASE = os.getenv('DEEPSEEK_API_BASE', 'https://api.deepseek.com')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
USE_DEEPSEEK_AI = os.getenv('USE_DEEPSEEK_AI', 'True') == 'True'

# ========== EMAIL ==========
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@novyra.agency')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# ========== ADMIN ==========
ADMINS = [
    ('Novyra Admin', os.getenv('ADMIN_EMAIL', 'admin@novyra.agency')),
]

# ========== LOGGING (optional but recommended for production) ==========
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
