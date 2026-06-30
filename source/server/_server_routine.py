import random
import sys
import numpy as np
import cv2

import io
import socket

import struct
import time

import urllib.request
import json      

NOTIFICATION_SEND_INTERVAL = 5
DATA_SEND_INTERVAL = 30

def server_routine(frame_queue, audio_queue,
                   room_temp, room_humid, baby_temp,
                   baby_is_crying, baby_feverish):
    '''
       Routine that:
           + Parses the data from all other routines
           + Synchronizes them if necessary
           + Sends the data to the server

       This routine needs continuous optimization. Do not overburden it.
       Maybe multithreading can be added?
    '''
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        import os
        for path in [".env", "../.env", "../../.env"]:
            if os.path.exists(path):
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
                break
    import os
    server_ip = os.environ.get('SERVER_IP', '192.168.11.16')

    # Connect a client socket to my_server:2000 (change my_server to the
    # hostname of your server)
    client_socket_video = socket.socket()
    client_socket_video.connect((server_ip, 2000))

    # Make a file-like object out of the connection
    connection_video = client_socket_video.makefile('wb')
    start_stream_video = False
    start_stream_audio = False
    want_data = b'w'
    send_data = b's'

    data_current_time = time.perf_counter()
    notification_current_time = time.perf_counter()
    
    notification_is_sent = False

    try:
        stream_video = io.BytesIO()
        while True:        

            try:
                if not start_stream_video:

                    # Possible addition of non-blocking arguments and select will be considered
                    answer = client_socket_video.recv(128)

                    if answer == want_data:
                        start_stream_video = True
                        client_socket_video.send(send_data)

                else:
                    frame = frame_queue.get()
                    _, encoded_frame = cv2.imencode('.jpg', frame)
                    stream_video.write(encoded_frame.tobytes())
                    # Write the length of the capture to the stream and flush to
                    # ensure it actually gets sent
                    connection_video.write(struct.pack('<L', stream_video.tell()))
                    connection_video.flush()
                    # Rewind the stream and send the image data over the wire
                    stream_video.seek(0)
                    connection_video.write(stream_video.read())
                    # Reset the stream for the next capture
                    stream_video.seek(0)
                    stream_video.truncate()
                    
                # Reading the values
                current_room_temperature = room_temp.value
                current_room_humidity = room_humid.value
                current_baby_temperature = baby_temp.value
                crying_detected = baby_is_crying.value
                fever_detected = baby_feverish.value

                if(time.perf_counter() - data_current_time > DATA_SEND_INTERVAL):
                    
                    data_current_time = time.perf_counter()
                
                    body = {'device_id': 26082007,
                            'room_temp': current_room_temperature,
                            'room_humd': current_room_humidity,
                            'baby_temp': current_baby_temperature}

                    myurl = "http://{}:8000/api/data".format(server_ip)
                    req = urllib.request.Request(myurl)
                    req.add_header('Content-Type', 'application/json')
                    jsondata = json.dumps(body)
                    jsondataasbytes = jsondata.encode('utf-8')
                    req.add_header('Content-Length', len(jsondataasbytes))
                    response = urllib.request.urlopen(req, jsondataasbytes)
                
                if fever_detected:
                    notification_code = 6
                elif crying_detected:
                    notification_code = 1
                else:
                    notification_code = 0
                
                if(time.perf_counter() - notification_current_time > NOTIFICATION_SEND_INTERVAL):
                    
                    notification_current_time = time.perf_counter()
      
                    body = {'device_id': 26082007,
                            'code': notification_code}

                    myurl = "http://{}:8000/api/notification".format(server_ip)
                    req = urllib.request.Request(myurl)
                    req.add_header('Content-Type', 'application/json')
                    jsondata = json.dumps(body)
                    jsondataasbytes = jsondata.encode('utf-8')
                    req.add_header('Content-Length', len(jsondataasbytes))
                    response = urllib.request.urlopen(req, jsondataasbytes)
                            
                                    
            except KeyboardInterrupt:
                raise RuntimeError
            
            except:
                print('Exception on Video Server')
                sys.stdout.flush()

    finally:
        
        connection_video.close()
        client_socket_video.close()

