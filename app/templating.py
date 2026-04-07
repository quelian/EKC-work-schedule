"""Jinja2-шаблоны относительно каталога `app/templates`."""
from fastapi.templating import Jinja2Templates

from .paths import BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.autoescape = True  # XSS protection for all templates
