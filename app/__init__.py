import click
from flask import (
    Flask, session, request, flash, redirect, url_for,
)
from app.config import Config
from app.extensions import db
from flask_migrate import Migrate

migrate = Migrate()  # no app yet

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    migrate.init_app(app,db)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        from app import models

    @app.before_request
    def _enforce_password_change():
        # A temporary password that is never changed is a permanent one.
        # Everything is blocked except the account page itself, logout,
        # and static files - otherwise the user cannot reach the form
        # that clears the flag.
        if not session.get('must_change_password'):
            return
        allowed = {'dashboard.my_account', 'auth.logout', 'static'}
        if request.endpoint in allowed:
            return
        flash("Set your own password before continuing.", "warning")
        return redirect(url_for('dashboard.my_account'))

    # CLI Command to create privileged users
    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("email")
    @click.argument("password")
    @click.option("--role", default="admin", help="Role: admin, field_officer, normal_user")
    def create_user(username, email, password, role):
        """Creates a user account directly from terminal."""
        from app.models import User
        
        user = User.query.filter((User.username == username) | (User.email_address == email)).first()
        if user:
            click.echo(f"Error: User with username '{username}' or email '{email}' already exists.")
            return

        new_user = User(
            username=username.strip().lower(),
            email_address=email.strip().lower(),
            role=role
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        click.echo(f"Successfully created {role}: {username}")

    return app