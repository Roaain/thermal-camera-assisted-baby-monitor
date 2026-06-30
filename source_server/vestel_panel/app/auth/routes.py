from flask import render_template, redirect, url_for, flash, request
from urllib.parse import urlsplit
from flask_login import login_user, logout_user, current_user
from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        redirect(url_for('index'))

    form = LoginForm(request.form)
    print(form.password)
    if request.method == 'POST' and form.validate():

        # Get the user
        user = User.query.filter_by(email=form.email.data).first()

        # Invalid login attempt
        if user is None or not user.check_password(form.password.data):
            print('problem')
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))


        print(user.name)
        print(user.check_password(form.password.data))

        # Log the user in :)
        login_user(user, remember=form.remember.data)
        next_page = request.args.get('next')

        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(next_page)

    else:
        return render_template('login.html', title='Sign In', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegisterForm()
    if request.method == 'POST' and form.validate_on_submit():

        user = User(name=form.name.data, surname=form.surname.data, email=form.email.data, device_id=form.deviceid.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congrats, you are now a registered user!')
        return redirect(url_for('auth.login'))
    else:
        return render_template('register.html', form=form)