from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR, get_settings


def test_alembic_imports_installed_library():
    assert callable(command.upgrade)
    assert callable(command.current)
    assert callable(command.heads)


def test_alembic_config_points_at_migrations():
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    location = cfg.get_main_option("script_location").replace("\\", "/")
    assert location.endswith("migrations") or location == "migrations"


def test_alembic_upgrade_head(client):
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    command.current(cfg)
    command.heads(cfg)
