# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 16:45:42 2019

@author: ASUS PC
"""
from flask import Flask, render_template, Response, stream_with_context

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
import time
from threading import Lock, Thread
import queue
import socket
import math
from datetime import datetime
import audioop


from threading import Thread

from camera3 import Camera



# emulated camera


# Raspberry Pi camera module (requires picamera package)
# from camera_pi import Camera
#server_socket = socket.socket()
#server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#server_socket.bind(('0.0.0.0', 3000))
#server_socket.listen(0)
#connection = server_socket.accept()[0]
#connection_file = connection.makefile('rb')
#frame_queue = queue.Queue(maxsize=1)
#stream_entered = False
#lock = Lock()
#app = Flask(__name__)

server_socket = None
connection_file = None
connection = None
frame_queue = queue.Queue(maxsize=5)
stream_entered = False
socket_open = False
lock = Lock()
app = Flask(__name__)


count = 1
check = -2
count_check = 0
frame_count = 0



# Generates the .wav file header for a given set of samples and specs
def genHeader(sampleRate, bitsPerSample, channels):
    #datasize = 2048 * 20 * channels * bitsPerSample // 8
    datasize = 2000 * 10 ** 6
    o = bytes("RIFF",'ascii')                                               # (4byte) Marks file as RIFF
    o += (datasize + 36).to_bytes(4,'little')                               # (4byte) File size in bytes excluding this and RIFF marker
    o += bytes("WAVE",'ascii')                                              # (4byte) File type
    o += bytes("fmt ",'ascii')                                              # (4byte) Format Chunk Marker
    o += (16).to_bytes(4,'little')                                          # (4byte) Length of above format data
    o += (1).to_bytes(2,'little')                                           # (2byte) Format type (1 - PCM)
    o += (channels).to_bytes(2,'little')                                    # (2byte)
    o += (sampleRate).to_bytes(4,'little')                                  # (4byte)
    o += (sampleRate * channels * bitsPerSample // 8).to_bytes(4,'little')  # (4byte)
    o += (channels * bitsPerSample // 8).to_bytes(2,'little')               # (2byte)
    o += (bitsPerSample).to_bytes(2,'little')                               # (2byte)
    o += bytes("data",'ascii')                                              # (4byte) Data Chunk Marker
    o += (datasize).to_bytes(4,'little')                                    # (4byte) Data size in bytes
    return o


def bar(camera, t):
    global stream_entered
    global lock
    global frame_queue
    global count
    global socket_open
    global connection_file
    global connection
    global check
    global count_check
    global frame_count
    while True:
        if not socket_open:
            server_socket = socket.socket()
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('0.0.0.0', 3000))
            #server_socket.listen(0)

            keep_on = True
            while keep_on:
                try:
                    keep_on = False
                    server_socket.listen(0)
                    connection = server_socket.accept()[0]  # .makefile('rb')
                except Exception as e:
                    print(e)
                    keep_on = True

            #connection = server_socket.accept()[0]  # .makefile('rb')
            connection_file = connection.makefile('rb')
            socket_open = True
            print("Socket is opened")

        elif stream_entered:
            start = t.time()
            try:
                print("start")
                frame_temp = camera.get_frame(connection_file, time)
                print("end")
            except Exception as e:
                print("An exception occured")
                print(e)
                socket_open = False
                stream_entered = False
                print("Waiting for socket")
                server_socket = socket.socket()
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', 3000))
                #server_socket.listen(0)

                keep_on = True
                while keep_on:
                    try:
                        keep_on = False
                        server_socket.listen(0)
                        connection = server_socket.accept()[0]  # .makefile('rb')
                    except Exception as e:
                        print(e)
                        keep_on = True

                #connection = server_socket.accept()[0]  # .makefile('rb')
                connection_file = connection.makefile('rb')
                socket_open = True
                count = 1
                check = -2
                count_check = 0
                frame_count = 0
                print("Socket opened")

            finish = t.time()
            if frame_temp is not None:

                for i in range(0, count):
                    frame_queue.put(frame_temp)



            finish = t.time()




@app.route("/wav")
def streamwav():
    global count
    global frame_queue
    global frame_count
    global check
    global count_check
    global frame_count
    global connection
    global connection_file
    global stream_entered
    global socket_open

    check = check + 1
    print("Check: " + str(check))

    if check != 0 and check % 2 == 0:
        count = count + 1
        count_check = count_check + 1
        print("Count: " + str(count))



    print('in')


    if not stream_entered and not socket_open:
        print("return plain text")
        Response.content_type = "text/plain"
        check = -2
        return """ Audio stream is not online. """


    elif not stream_entered and socket_open:
        # Start streaming
        connection.sendall(b'w')
        print('I am in01')

        data = connection.recv(128)
        print('I am in1')

        # print(data)

        if data == b's':
            print('I am in')
            stream_entered = True
    if stream_entered:
        return Response(gen_audio(), mimetype="audio/x-wav")

def gen_audio():

    global count
    global frame_queue
    global frame_count
    global check
    global count_check
    global frame_count
    global connection
    global connection_file

    sampleRate = 48000
    bitsPerSample = 16
    print('in generate')

    channels = 2
    wav_header = genHeader(sampleRate, bitsPerSample, channels)
    frame = frame_queue.get()
    prev = frame
    chunk = wav_header + frame
    #chunk = audioop.mul(chunk, 2, 2)

    yield (chunk)

    while True:
        chunk = frame_queue.get()
        while(prev == chunk):
            chunk = frame_queue.get()
            #chunk = audioop.mul(chunk, 2, 2)
            #if(count_check != count):
            #    count = count_check
            print("Count is now: " +  str(count))
            frame_count = 0
        #if(frame_count == count):
        #    if(count == count_check):
        #        count_check = count_check - 1
        #        frame_count = 0
        yield (chunk)
        prev = chunk


def foo():
    cert_file = os.path.expanduser(os.environ.get('SSL_CERT_FILE', ''))
    key_file = os.path.expanduser(os.environ.get('SSL_KEY_FILE', ''))
    app.run('0.0.0.0', port=4000, debug=False, threaded=True, ssl_context=(cert_file, key_file))



if __name__ == '__main__':
    dum = Thread(target= bar, args=(Camera(), time))
    dum.start()
    foo()