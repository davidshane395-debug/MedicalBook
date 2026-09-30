import os
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-key-before-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        user = quote_plus(os.getenv("DB_USER", "root"))
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = os.getenv("DB_PORT", "3306")
        name = os.getenv("DB_NAME", "medical_book_shop")
        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"
    elif db_url.startswith("mysql://"):
        db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)

    # Aiven supplies `ssl-mode=REQUIRED`, while PyMySQL expects SSL through
    # connect_args. Normalize the URL so the Aiven Service URI can be pasted
    # directly into DATABASE_URL.
    ssl_required = False
    url_parts = urlsplit(db_url)
    clean_query = []
    for key, value in parse_qsl(url_parts.query, keep_blank_values=True):
        if key.lower() in {"ssl-mode", "sslmode"}:
            ssl_required = value.upper() in {"REQUIRED", "REQUIRE", "VERIFY_CA", "VERIFY_IDENTITY"}
        else:
            clean_query.append((key, value))
    db_url = urlunsplit((url_parts.scheme, url_parts.netloc, url_parts.path, urlencode(clean_query), url_parts.fragment))

    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    if ssl_required:
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {"ssl": {"check_hostname": False}}
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join("static", "uploads"))

