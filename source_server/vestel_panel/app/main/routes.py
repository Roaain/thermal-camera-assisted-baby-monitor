from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, current_app, Response
from flask_login import current_user, login_user, logout_user, login_required
from app import db
from app.models import User, Data, Notification, Device
from app.main import bp


@bp.route('/')
@bp.route('/index')
@login_required
def index():

	device_props = Device.query.filter_by(id=current_user.device_id).first()
	notif_count = Notification.query.filter_by(user_id=current_user.id).count()
	data_collection = Data.query.filter_by(device_id=current_user.device_id).order_by(Data.timestamp.desc()).limit(12).all()


	return render_template('index.html', title='Dashboard', device_props = device_props, notif_count = notif_count, data_collection = data_collection)

@bp.route('/user')
@login_required
def user():
	return render_template('user.html', title = 'User Settings')

@bp.route('/statistics')
@login_required
def statistics():
	data_collection = Data.query.filter_by(device_id=current_user.device_id).order_by(Data.timestamp.desc()).limit(12)
	return render_template('statistics.html', title = 'Statistics', data_collection=data_collection)

@bp.route('/video')
@login_required
def video():
	#Video feed here
	return render_template('video.html', title = 'Video Stream')

@bp.route('/alarms')
@login_required
def alarms():
	data_collection = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
	return render_template('alarms.html', title = 'Alarms', data_collection=data_collection)

@bp.route('/device_config')
@login_required
def device_config():
	return render_template('device_config.html', title = 'Device Configuration')

@bp.route('/help')
@login_required
def help():
	return render_template('help.html', title = 'Help')