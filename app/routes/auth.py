from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.extensions import db
from app.models import User, Organization
from app.utils.audit import log_action, log_login

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        email_address = request.form.get('email_address', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirmPassword', '').strip()
        organization_id = request.form.get('organization_id')

        if not username or not password or not email_address:
            return render_template('Register.html', error="Please fill in all required fields!")

        if confirm_password != password:
            return render_template('Register.html', error="Passwords do not match!")

        existing_user = User.query.filter(
            (User.username == username) | (User.email_address == email_address)
        ).first()

        if existing_user:
            return render_template('Register.html', error="Username or Email already exists!")

        new_user = User(
            username=username,
            email_address=email_address,
            role="normal_user",
            organization_id=int(organization_id) if organization_id else None
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('auth.login'))

    organizations = Organization.query.all()
    return render_template("Register.html", organizations=organizations)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.user_id
            session['username'] = user.username
            session['role'] = user.role
            session['cenro'] = user.cenro
            session['cenro'] = user.cenro
            log_login(user.username, True, user.role, user.user_id)             
            return redirect(url_for('dashboard.index'))
        else:
            log_login(username, False)
            return render_template('Log_in.html', error="Incorrect Username or Password")

    return render_template("Log_in.html")


@auth_bp.route('/logout')
def logout():
    log_action('logout', 'users', session.get('user_id'), commit=True)
    session.clear()
    return redirect(url_for('auth.login'))