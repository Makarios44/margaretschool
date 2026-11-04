"""Configurações do projeto Margaret School."""
import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Em produção, defina DJANGO_SECRET_KEY, DJANGO_DEBUG=0 e DJANGO_ALLOWED_HOSTS.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-only-troque-esta-chave-em-producao"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

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

# Fotos das galerias ficam FORA de MEDIA_ROOT: só saem pelo sistema, respeitando quem pode ver cada álbum.
MIDIA_PRIVADA = BASE_DIR / "midia_privada"

# Fotos dos alunos (enviadas pela secretaria)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

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
