"""Configurações do projeto Margaret School."""
import os
import sys
from decimal import Decimal
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _lista(nome, padrao=""):
    return [v.strip() for v in os.environ.get(nome, padrao).split(",") if v.strip()]


def _sim(nome, padrao):
    return os.environ.get(nome, "1" if padrao else "0").strip().lower() in ("1", "true", "sim", "yes")


# Em produção, defina DJANGO_DEBUG=0, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS e DATABASE_URL (veja .env.example).
DEBUG = _sim("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY em produção.")
    SECRET_KEY = "dev-only-troque-esta-chave-em-producao"
ALLOWED_HOSTS = _lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Origens com esquema, ex.: https://margaretschool.com.br,https://www.margaretschool.com.br
CSRF_TRUSTED_ORIGINS = _lista("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "alunos",
    "matriculas",
    "financeiro",
    "documentos",
    "calendario",
    "pre_matriculas",
    "administracao",
    "divulgacao",
    "frequencia",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "administracao.middleware.ConfiguracaoMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.escola",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL via DATABASE_URL, ex.: postgres://usuario:senha@localhost:5432/margaret_school
# Sem DATABASE_URL (só em desenvolvimento) usa o SQLite local.
if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": dj_database_url.config(
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
        ssl_require=_sim("DB_SSL_REQUIRE", False),
    )}
elif DEBUG:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    raise ImproperlyConfigured("Defina DATABASE_URL (PostgreSQL) em produção.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Em produção os arquivos estáticos saem pelo WhiteNoise, comprimidos e com nome versionado
# (rode "python manage.py collectstatic" a cada deploy).
# Se o collectstatic não rodou (sem manifest), o WhiteNoise serve direto das pastas do projeto
# em vez de derrubar as páginas com "Missing staticfiles manifest entry".
_MANIFEST_OK = (STATIC_ROOT / "staticfiles.json").exists() or "collectstatic" in sys.argv
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or not _MANIFEST_OK
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_USE_FINDERS = DEBUG or not _MANIFEST_OK

# Fotos das galerias ficam FORA de MEDIA_ROOT: só saem pelo sistema, respeitando quem pode ver cada álbum.
MIDIA_PRIVADA = Path(os.environ.get("DJANGO_MIDIA_PRIVADA", BASE_DIR / "midia_privada"))

# Uploads (fotos dos alunos, comprovantes, banners). Saem pelo sistema (core.views.midia):
# banners dos anúncios são públicos; o resto só para a equipe logada.
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Autenticação
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

# Dados da escola usados nas fichas e contratos impressos.
# Preencha pelas variáveis de ambiente ou direto aqui.
ESCOLA = {
    "nome": os.environ.get("ESCOLA_NOME", "Margaret School"),
    "cnpj": os.environ.get("ESCOLA_CNPJ", ""),
    "endereco": os.environ.get("ESCOLA_ENDERECO", "Rua Travessa dos Flamingos, nº 79 — Praia da Pipa"),
    "cidade": os.environ.get("ESCOLA_CIDADE", "Tibau do Sul/RN"),
    "telefone": os.environ.get("ESCOLA_TELEFONE", "(84) 99165-8059"),
    # Página inicial (editáveis em Administração → Dados da escola)
    "instagram": os.environ.get("ESCOLA_INSTAGRAM", ""),
    "slogan": os.environ.get("ESCOLA_SLOGAN", "Escolher uma escola vai muito além do ensino."),
    "apresentacao": os.environ.get(
        "ESCOLA_APRESENTACAO",
        "Escola bilíngue na Praia da Pipa. Mais de 10 anos alfabetizando crianças com carinho e dedicação."),
    # Dados exigidos nos documentos escolares oficiais:
    "inep": os.environ.get("ESCOLA_INEP", ""),                      # código INEP da escola
    "mantenedora": os.environ.get("ESCOLA_MANTENEDORA", ""),
    "ato_autorizacao": os.environ.get("ESCOLA_ATO_AUTORIZACAO", ""),  # ato de credenciamento/autorização
    "diretor": os.environ.get("ESCOLA_DIRETOR", ""),
    "diretor_ato": os.environ.get("ESCOLA_DIRETOR_ATO", ""),          # ato de nomeação/designação
    "secretario": os.environ.get("ESCOLA_SECRETARIO", ""),
    "secretario_ato": os.environ.get("ESCOLA_SECRETARIO_ATO", ""),
}

# Encargos por atraso (use 0 para desligar). Mantenha iguais ao que consta no contrato.
FINANCEIRO = {
    "multa_percentual": Decimal(os.environ.get("FIN_MULTA_PERCENTUAL", "2")),
    "juros_mensal_percentual": Decimal(os.environ.get("FIN_JUROS_MENSAL_PERCENTUAL", "1")),
}

# Região usada para carregar os feriados estaduais e municipais do calendário.
# Feriados municipais pré-cadastrados: Natal/RN. Em outra cidade, cadastre os municipais
# pela tela de eventos (marque "Repete todo ano").
CALENDARIO = {
    "uf": os.environ.get("CALENDARIO_UF", "RN"),
    "municipio": os.environ.get("CALENDARIO_MUNICIPIO", "Tibau do Sul"),
}


# ---------- Segurança em produção ----------
if not DEBUG:
    # Atrás de um proxy (Nginx, Render, Railway...) que repassa X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _sim("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _sim("DJANGO_HSTS_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = False
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 10  # 10 horas: um dia de trabalho na secretaria

# Logs no console (o servidor/serviço de hospedagem recolhe a saída).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simples": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simples"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {"django": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
                           "propagate": False}},
}
