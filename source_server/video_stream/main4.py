# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 16:45:42 2019

@author: ASUS PC
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
from flask import Flask, render_template, Response

import time
from threading import Lock, Thread
import queue
import socket

from threading import Thread





# emulated camera
from camera3 import Camera

# Raspberry Pi camera module (requires picamera package)
# from camera_pi import Camera
#server_socket = socket.socket()
#server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#server_socket.bind(('0.0.0.0', 2000))
#server_socket.listen(0)
#connection = server_socket.accept()[0] #.makefile('rb')
#connection_file = connection.makefile('rb')
server_socket = None
connection_file = None
connection = None
frame_queue = queue.Queue(maxsize=5)
stream_entered = False
socket_open = False
lock = Lock()
app = Flask(__name__)
import urllib.request
import json

def send_device_status(cond):

    body = {'device_id': 26082007, 'status': cond}
    server_ip = os.environ.get('SERVER_IP', '192.168.11.16')
    myurl = f"http://{server_ip}:8000/api/updateDeviceStatus"
    req = urllib.request.Request(myurl)
    req.add_header('Content-Type', 'application/json')
    jsondata = json.dumps(body)
    jsondataasbytes = jsondata.encode('utf-8')
    req.add_header('Content-Length', len(jsondataasbytes))
    print (jsondataasbytes)
    response = urllib.request.urlopen(req, jsondataasbytes)


def bar(camera, t):
    global stream_entered
    global lock
    global frame_queue
    global server_socket
    global connection_file
    global connection
    global socket_open
    first_time = True
    while True:
        if not socket_open:
            if first_time:
                t.sleep(2)
            send_device_status(socket_open)
            server_socket = socket.socket()
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', 2000))

            keep_on = True
            while keep_on:
                try:
                    keep_on = False
                    server_socket.listen(0)
                    connection = server_socket.accept()[0]  # .makefile('rb')
                    print('I am here')
                except Exception as e:
                    print(e)
                    keep_on = True

            # connection = server_socket.accept()[0]  # .makefile('rb')

            connection_file = connection.makefile('rb')
            socket_open = True
            send_device_status(socket_open)

        elif stream_entered:
            start = t.time()
            try:
                frame_temp = camera.get_frame(connection_file, time)
            except Exception as e:
                print("An exception occured")
                print(e)
                socket_open = False
                stream_entered = False
                send_device_status(socket_open)
                print("Waiting for socket")
                server_socket = socket.socket()
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', 2000))

                keep_on = True
                while keep_on:
                    try:
                        keep_on = False
                        server_socket.listen(0)
                        connection = server_socket.accept()[0]
                    except Exception as e:
                        print(e)
                        keep_on = True

                #connection = server_socket.accept()[0]  # .makefile('rb')
                connection_file = connection.makefile('rb')
                socket_open = True
                send_device_status(socket_open)
                print("Socket opened")



            if frame_temp is not None:
                lock.acquire()
                frame_queue.put(frame_temp)
                lock.release()


            finish = t.time()




@app.route('/')
def index():
    """Video streaming home page."""
    print('x')
    return render_template('index.html')



def gen():
    global frame_queue
    global lock
    """Video streaming generator function."""

    while True:
        frame = frame_queue.get()
        if frame is not None:
            yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            try:
                file_name = "root/video_stream/RefreshImage.jpg"
                with open(file_name, 'rb') as img_file:
                    frame_temp = img_file.read()
            except Exception as e:
                print(e)
                file_name = "RefreshImage.jpg"
                with open(file_name, 'rb') as img_file:
                    frame_temp = img_file.read()
            frame = frame_temp
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def gen2(frame):
    yield (b'--frame\r\n'
           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')



@app.route('/video_feed')
def video_feed():
    print('in')
    global stream_entered
    global socket_open
    global connection

    if not stream_entered and not socket_open:
        try:
            file_name = "root/video_stream/RefreshImage.jpg"
            with open(file_name, 'rb') as img_file:
                frame_temp = img_file.read()
        except Exception as e:
            print(e)
            file_name = "RefreshImage.jpg"
            with open(file_name, 'rb') as img_file:
                frame_temp = img_file.read()

        return Response(gen2(frame_temp),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    elif not stream_entered and socket_open:
        # Start streaming
        connection.sendall(b'w')
        print('I am in01')

        data = connection.recv(128)
        print('I am in1')




        if data == b's':
            print('I am in')
            stream_entered = True

    if stream_entered:
        print(stream_entered)
        """Video streaming route. Put this in the src attribute of an img tag."""
        return Response(gen(),
                mimetype='multipart/x-mixed-replace; boundary=frame')



def foo():
    cert_file = os.environ.get('SSL_CERT_FILE')
    key_file = os.environ.get('SSL_KEY_FILE')
    # Expand ~ in paths if present
    if cert_file:
        cert_file = os.path.expanduser(cert_file)
    if key_file:
        key_file = os.path.expanduser(key_file)
    ssl_ctx = (cert_file, key_file) if cert_file and key_file else None
    if ssl_ctx is None:
        print('WARNING: SSL_CERT_FILE / SSL_KEY_FILE not set, running without HTTPS')
    app.run('0.0.0.0', port=5000, debug=False, threaded=True, ssl_context=ssl_ctx)



if __name__ == '__main__':
    dum = Thread(target= bar, args=(Camera(), time))
    dum.start()
    foo()
















