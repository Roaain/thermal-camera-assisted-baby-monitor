import random
from queue import Empty
import sys
import cv2
import adafruit_dht
from control.timed_threads import record_temp_humid_offset, calculate_transform_matrix, detect_face_location, record_baby_temperature
from threading import Timer
import serial
from collections import deque
import os

class MockSerial:
    def __init__(self, *args, **kwargs): pass
    def readline(self):
        import time
        time.sleep(0.1)
        return b"b'45.0,24.0\\r\\n'"

def control_routine(bgr_thermal_queue,
                    shared_transform_matrix,
                    room_temp, room_humid, baby_temp, aux_temperature,
                    temp_dict, faces_queue, baby_feverish):
    
    '''
    Routine that:
        + Checks the room temperature and humidity,
        + Detects the baby temperature,
        + If possible, recognizes the face of the baby,
        + Creates an alignment vector centered on the baby.
       
    Please be careful on modifying this part, as arguments except for the
    bgr_thermal_queue are not pythonic variables but rather Value or Arrays
    which behaves like an object, including a value (ctype) and a lock. This
    prevents any usual multiprocessing pitfalls, so always try to use
    a 'with' clause when utilizing them.
    '''
    face_detect_interval = 1.0
    room_fpa_temp_interval = 5.0
    alignment_interval = 18000.0
    baby_temp_interval = 1.0
    
    baby_temp_deque = deque([0]*20, 20)
    
    import os
    face_detector = cv2.CascadeClassifier(os.path.join(os.path.dirname(__file__), 'haarcascade_frontalface_default.xml'))
    if os.path.exists('/dev/ttyUSB0'):
        DHT_22 = serial.Serial('/dev/ttyUSB0', 9600, timeout = 3)
    else:
        print("Using MockSerial for DHT_22")
        DHT_22 = MockSerial()
    
    try:
        
        bgr_frame, thermal_frame = bgr_thermal_queue.get()
        
        # Initiate and start timers.
        detect_face_timer = Timer(1.0, detect_face_location, [bgr_frame, face_detector, faces_queue])
        detect_face_timer.start()
        
        temp_hum_timer = Timer(0.05, record_temp_humid_offset, [DHT_22, room_temp,
                                                                room_humid, aux_temperature, temp_dict, thermal_frame])
        temp_hum_timer.start()
        
        baby_temp_timer = Timer(5.0, record_baby_temperature, [bgr_frame, thermal_frame, baby_temp,
                                                               face_detector, shared_transform_matrix, aux_temperature,
                                                               baby_temp_deque, baby_feverish])
        baby_temp_timer.start()
        
        alignment_timer = Timer(18000.0, calculate_transform_matrix, [shared_transform_matrix,
                                                                   bgr_frame, thermal_frame])
        alignment_timer.start()
                
        while True:
            
            # Get the frames
            try:
                # If no frame is fed to the queue by the video process for 10 seconds,
                # the method timeouts and gives an exception, which is caught below.
                bgr_frame, thermal_frame = bgr_thermal_queue.get(timeout = 10)
                
                if not detect_face_timer.is_alive():
                    print('face thread finished')
                    sys.stdout.flush()
                    detect_face_timer.cancel()
                    detect_face_timer = Timer(face_detect_interval, detect_face_location, [bgr_frame, face_detector, faces_queue])
                    detect_face_timer.start()
                
                if not baby_temp_timer.is_alive():
                    print('baby temp thread finished')
                    sys.stdout.flush()
                    baby_temp_timer.cancel()
                    baby_temp_timer = Timer(baby_temp_interval, record_baby_temperature, [bgr_frame, thermal_frame, baby_temp,
                                                                                          face_detector, shared_transform_matrix,
                                                                                          aux_temperature, baby_temp_deque, baby_feverish])
                    baby_temp_timer.start()
                
                if not temp_hum_timer.is_alive():
                    print('temp thread finished')
                    sys.stdout.flush()
                    temp_hum_timer.cancel()
                    temp_hum_timer = Timer(room_fpa_temp_interval, record_temp_humid_offset, [DHT_22, room_temp,
                                                               room_humid, aux_temperature, temp_dict, thermal_frame])
                    temp_hum_timer.start()
                
                if not alignment_timer.is_alive():
                    print('alignment thread finished')
                    sys.stdout.flush()
                    alignment_timer.cancel()
                    alignment_timer = Timer(alignment_interval, calculate_transform_matrix, [shared_transform_matrix,
                                                                               bgr_frame, thermal_frame])
                    alignment_timer.start()
                
            except KeyboardInterrupt:
                raise RuntimeError
            
            except Empty:
                print('Timeout -- frames could not be parsed to the control routine')
                sys.stdout.flush()
        
    finally:
        # Cancel the timers
        temp_hum_timer.cancel()
        alignment_timer.cancel()
        detect_face_timer.cancel()
        baby_temp_timer.cancel()
        
        print('control routine stopped.')
        sys.stdout.flush()
        