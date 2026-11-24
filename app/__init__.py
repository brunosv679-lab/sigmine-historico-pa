"""
Application Factory — cria e configura a aplicação Flask.
"""
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db


def create_app(config_object: Config = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )

    # Configuração
    if config_object is None:
        config_object = Config()
    app.config.from_object(config_object)

    # ProxyFix para suportar proxy reverso com subrota (ex: /sigmine/)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

    # Extensões
    db.init_app(app)

    # Blueprints
    from .controllers.web_controller import web_bp
    from .controllers.api_controller import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
