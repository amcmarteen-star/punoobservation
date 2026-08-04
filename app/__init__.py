import click
from flask import Flask
from app.config import Config
from app.extensions import db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    with app.app_context():
        from app import models
        db.create_all()

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