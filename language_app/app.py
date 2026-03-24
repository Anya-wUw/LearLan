from flask import Flask, redirect, url_for, session
from config import Config
from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.groups import groups_bp
from routes.cards import cards_bp
from routes.dialogues import dialogues_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.jinja_env.globals["zip"] = zip
    app.jinja_env.filters["ord"] = ord

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(cards_bp)
    app.register_blueprint(dialogues_bp)

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("groups.dashboard"))
        return redirect(url_for("auth.login"))

    return app


app = create_app()

if __name__ == "__main__":
    ### app.run(debug=True)
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
