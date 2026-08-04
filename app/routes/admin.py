# app/routes/admin.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.extensions import db
from app.models import User
from app.utils.decorators import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_field_officer():
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email_address', '').strip().lower()
    password = request.form.get('password')
    role = request.form.get('role', 'field_officer') # Admin assigns role here

    existing_user = User.query.filter(
        (User.username == username) | (User.email_address == email)
    ).first()

    if existing_user:
        flash("Username or Email already exists.", "danger")
        return redirect(url_for('admin.manage_users'))

    new_user = User(
        username=username,
        email_address=email,
        role=role
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash(f"User {username} successfully created as {role}.", "success")
    return redirect(url_for('admin.manage_users'))