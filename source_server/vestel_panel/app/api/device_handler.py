from flask import jsonify, request, url_for
from app import db
from app.models import Data,Notification,User,Subscriber, Device
from app.api import bp
from app.api.errors import bad_request
import json
from pywebpush import webpush, WebPushException
import logging

@bp.route('/data', methods=['POST'])
def createDataEntry():
    data = request.get_json() or {}
    print(data)

    if 'device_id' not in data or 'room_temp' not in data or 'room_humd' not in data or 'baby_temp' not in data:
        return bad_request('Corrupted data!')

    #Create data object
    dataEntry = Data()
    dataEntry.from_dict(data)

    print(dataEntry)

    #Update db
    db.session.add(dataEntry)
    db.session.commit()

    #Return the response
    response = jsonify()
    response.status_code = 201
    return response

@bp.route('/notify')
def notify(message):
    WEBPUSH_VAPID_PRIVATE_KEY = 'MGSKy99ZwpSUn_V89wKUsL5mtNij3fbnZzpDKkHddMY'

    items = Subscriber.query.filter_by(is_active = True).all()
    count = 0

    for item in items:
        try:
            print(type(item))
            a = json.loads(item.subscription_info)

            webpush(
                subscription_info=a,
                data=message,
                vapid_private_key=WEBPUSH_VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": "mailto:support2@vestelagu.site",
                    "aud": "https://vestelagu.site"
                }
            )
            count += 1
        except WebPushException as ex:
            logging.exception("webpush fail")


    return "{} notification(s) sent".format(count)

@bp.route('/notification', methods=['POST'])
def createNotificationEntry():

    data = request.get_json() or {}
    print(data)

    if 'device_id' not in data or 'code' not in data:
        return bad_request('Corrupted data!')

    device_id = data['device_id']
    code = data['code']

    device = Device.query.filter_by(id= device_id).first()
    currentStatus = device.baby_status

    print(currentStatus)
    print(code)


    if currentStatus != code:

        #Create notification object
        users = User.query.filter_by(device_id=device_id).all()
        
        #Update
        device.baby_status = code
        db.session.commit()


        for u in users:
            notificationEntry = Notification()
            notifData = dict()

            notifData['user_id'] = u.id
            notifData['code'] = code

            notificationEntry.from_dict(notifData)

            # Update db
            db.session.add(notificationEntry)
            db.session.commit()

        #Update db
        #db.session.add(notificationEntry)
        #db.session.commit()

        #Return the response
        message = "Alarm"

        if code == 1:
            message = "Your baby seems like not sleeping, want to check? :)"
        elif code == 6:
            message = "Fever risk, please check your baby :)"
        elif code == 0:
            message = "Your dear is OK :)"

        print(message)

        notify(message)

    response = jsonify()
    response.status_code = 201


    return response


@bp.route('/subscribe', methods=['POST'])
def subscribe():

    info = (request.data).decode('utf-8')
    print(info)

    print(info)
    print(type(info))

    subsEntry = Subscriber()
    subsEntry.set_subsinfo(info)

    item = Subscriber.query.filter_by(subscription_info= info).first()
    if item is None:

        db.session.add(subsEntry)
        db.session.commit()
        print('Subscription created!')

    else:
        print('Subscription exists!')

    response = jsonify()
    response.status_code = 201
    response.id = subsEntry.id

    return response


@bp.route('/updateDeviceStatus', methods=['POST'])
def updateDeviceStatus():

    data = request.get_json() or {}

    device_id = data['device_id']
    stat = data['status']

    #Create notification object
    device = Device.query.filter_by(id=device_id).first()
    if device is None:
        device = Device(id=str(device_id), device_status=stat, baby_status=0)
        db.session.add(device)
    else:
        device.device_status = stat
    db.session.commit()

    response = jsonify()
    response.status_code = 201

    return response