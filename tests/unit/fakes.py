"""Valores ficticios compartidos por los tests unitarios."""

# Valor con forma de secreto, para verificar que nunca aparece en errores ni logs.
FAKE_DATABASE_PASSWORD = "S3cretPassw0rd"  # noqa: S105 — ficticio a propósito
FAKE_DATABASE_URL = (
    f"postgresql+psycopg://bot_user:{FAKE_DATABASE_PASSWORD}"
    "@db.internal.example:5432/bot"
)

# Puerto cerrado en loopback: la conexión se rechaza sin salir a la red.
UNREACHABLE_DATABASE_URL = (
    f"postgresql+psycopg://bot_user:{FAKE_DATABASE_PASSWORD}@127.0.0.1:1/bot"
)
