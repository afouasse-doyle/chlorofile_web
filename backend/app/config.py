import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env partagé avec flaskapp, localisé par la variable système CHLOROFILE_ENV_PATH.
# Si absente, pydantic-settings se rabat sur les variables d'environnement brutes.
_ENV_PATH = os.environ.get("CHLOROFILE_ENV_PATH")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL (partagé avec le système Flask — même serveur, même base)
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_db: str = "chlorofile2"
    pg_sslmode: str = "require"

    # Utilisateur dédié au portail (accès appweb uniquement)
    web_pg_user: str
    web_pg_pass: str

    # Sécurité portail
    web_secret_key: str                       # clé de signature JWT
    web_allowed_origins: str = "http://localhost:5173"
    jwt_algorithm: str = "HS256"
    # Durées de session (contrôlées côté serveur via appweb.user_sessions)
    session_idle_minutes: int = 30            # déconnexion après inactivité
    session_absolute_minutes: int = 480       # durée max d'une session (cap dur, 8 h)
    session_touch_seconds: int = 60           # throttle des UPDATE last_seen_at

    # Anti-brute-force sur le login (fenêtre glissante)
    login_lockout_minutes: int = 15           # fenêtre d'observation + durée du verrouillage
    login_max_attempts_email: int = 5         # échecs max par email avant verrouillage
    login_max_attempts_ip: int = 20           # échecs max par IP (spray multi-comptes)

    # App
    debug: bool = False
    log_file: str = "logs/chlorofile_web.log"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.web_pg_user}:{self.web_pg_pass}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
            f"?sslmode={self.pg_sslmode}"
        )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.web_allowed_origins.split(",")]


def get_settings() -> Settings:
    # Le .env est chargé via CHLOROFILE_ENV_PATH dans l'environnement Windows.
    # pydantic-settings lit les variables d'environnement directement.
    return Settings()  # type: ignore[call-arg]
