import random
from queue import Empty
from skimage import transform
from control.transform_matrix import _calculate_transform_matrix
import sys
import cv2
import adafruit_dht
import numpy as np
from scipy import stats
from subprocess import Popen, PIPE
import time

def record_baby_temperature(bgr_frame, thermal_frame, baby_temp, face_detector, shared_transform_matrix,
                            aux_temperature, baby_temp_deque, baby_feverish):

    # First, try to detect faces. If you can, get the maximum value on the face.
    # If face cannot be detected, detect blob and get ROI.

        # Acquire the transform matrix and if it is new, create transform object
    with shared_transform_matrix.get_lock(): 
        transform_matrix = np.array(shared_transform_matrix).reshape((2,6))
    transform_obj = transform.PolynomialTransform(transform_matrix)
    
    # Rorate for demo purposes
    rotat = cv2.rotate(bgr_frame, cv2.ROTATE_90_CLOCKWISE)
    faces = face_detector.detectMultiScale(rotat,1.05,1, minSize = (10,10),  maxSize = (150,150))

    if not isinstance(faces,tuple):  # if faces are returned
        
        rotated_back_faces = []
        for x,y,w,h in faces:
            zeros = np.zeros_like(rotat)
            zeros[y,x] = 1
            rotat_zeros = cv2.rotate(zeros, cv2.ROTATE_90_COUNTERCLOCKWISE)
            y_rotat,x_rotat,_ = np.unravel_index(rotat_zeros.argmax(), rotat_zeros.shape)
            rotated_back_faces.append((x_rotat, y_rotat, h, w))
        
        faces = rotated_back_faces
        # filter by location
        faces = [(x,y,w,h) for x,y,w,h in faces if (180 >= x >= 60) and (135 >= y >= 45)]
        
        if faces:
            # Take the first face.
            x,y,w,h = faces[0]
            x,y = (transform_obj(np.array([x,y]).reshape((1,2))).astype(int))[0]
            w,h = int(w*thermal_frame.shape[1]/bgr_frame.shape[1]), int(h*thermal_frame.shape[0]/bgr_frame.shape[0])
            
            face = thermal_frame[y-h:y,x:x+w]
            if face.size > 0:
                new_temp = np.max(face) * 0.0403 + aux_temperature.value * 1.2803 - 322.895
                if 70 >= new_temp >= 20:
                    baby_temp.value = new_temp
            
            print('******************************')
            print('Face detected. Max Temp: {}'.format(baby_temp.value))
            print('******************************')
            sys.stdout.flush()
        else:
            new_temp = np.max(thermal_frame[15:45,20:60]) * 0.0403 + aux_temperature.value * 1.2803 - 322.895
            if 70 >= new_temp >= 20:
                baby_temp.value = new_temp
            
            print('******************************')
            print('Face not detected. Max Temp: {}'.format(baby_temp.value))
            print('******************************')
            sys.stdout.flush()
            
    else:
        new_temp = np.max(thermal_frame[15:45,20:60]) * 0.0403 + aux_temperature.value * 1.2803 - 322.895
        if 70 >= new_temp >= 20:
            baby_temp.value = new_temp
        
        print('******************************')
        print('Face not detected. Max Temp: {}'.format(baby_temp.value))
        print('******************************')
        sys.stdout.flush()
    
    baby_temp_deque.append(baby_temp.value)
    peak_count = np.count_nonzero( np.array(baby_temp_deque) > 33.5)
            
    if( peak_count > 16):
        baby_feverish.value = True
    else:
        baby_feverish.value = False
    

def record_temp_humid_offset(DHT_22,
                             room_temp, room_humid, AUX_temp,
                             temp_dict, thermal_frame):
    '''
    Get the room temperature and humidity from the DHT sensor, calculate
    the temperature offset of the model with redpect to the room temperature.

    Parameters
    ----------
    DHT_sensor : int(?)
        DHT sensor value parsed from Adafruit_DHT.DHT22 property. Probably integer. 
    DHT_pin : int
        Pin of the DHT sensor.
    room_temp : multiprocessing.Value
        Shared memory of room temperature with lock.
    room_humid : multiprocessing.Value
        Shared memory of room humidity with lock.
    temp_offset : multiprocessing.Value
        Shared memory of temperature offset with lock.
    temp_dict : dictionary
        Piecewise quadratic mapping of the temperature model.
    thermal_frame: ndarray
        Thermal frame to calculate the offset of the model.
    
    Returns
    -------
    None
    
    '''
    print('thread 1')
    sys.stdout.flush()
    
    # Get room humidity and temperature
    try:
        data = False
        while (not data) or data == '':
            data = str(DHT_22.readline())[2:-5]
            room_humidity, room_temperature = data.split(',')
    except:
        room_temperature = '24.3'
        room_humidity = '36.6'
        print('DHT string exception')
    
    import os
    aux_temp_path = os.path.join(os.path.dirname(__file__), 'raspberrypi_video', 'AUX_temp')
    p = Popen([f'sudo {aux_temp_path}'], shell=True, stdout=PIPE, stdin=PIPE)
    try:
        chip_temp_raw = int(p.stdout.readline().strip())
    except ValueError:
        chip_temp_raw = 29000 # Dummy value 290K = 17C
    chip_temp = (chip_temp_raw/100)-273
    print('***************************************')

    if room_humidity is not None:
    
        room_temp.value = float(room_temperature)
        room_humid.value = float(room_humidity)
        
        AUX_temperature = chip_temp + 5 # add offset
        AUX_temp.value = float(round(AUX_temperature, 3))
        
        print('Room Temp: {}'.format(float(room_temperature)))
        print('Room Humid: {}'.format(float(room_humidity)))
        print('AUX Temp: {}'.format(float(round(AUX_temperature, 3))))
        print('***************************************')
        sys.stdout.flush()


def calculate_transform_matrix(shared_transform_matrix,
                               bgr_frame, thermal_frame):
    '''
    Get the room temperature and humidity from the DHT sensor, calculate
    the temperature offset of the model with redpect to the room temperature.

    Parameters
    ----------
    thermal_frame: ndarray
        Thermal frame to calculate the offset of the model.
    bgr_frame: ndarray
        Thermal frame to calculate the offset of the model.
    shared_transform_matrix : multiprocessing.Array
        Shared memory of transformation matrix with lock.
    
    
    Returns
    -------
    None
    
    '''
    print('thread 2')
    sys.stdout.flush()
            
    # Process the thermal frame
    normalized_thermal = cv2.normalize(thermal_frame, None, 0, 255, cv2.NORM_MINMAX)
    
    # Increasing the scale factor makes the canny hysteresis thresholds'
    # calculation unstable. 3 is determined to be an empirically sufficient
    # number for matrix calculation.
    scale_factor_of_thermal = 3
    
    # override max height and width. 
    max_height = 60*scale_factor_of_thermal
    
    # Expand-reduce frames to have the same size. Do not apply Gaussian smoothing,
    # since a total-variation denoising will be done later
    if(bgr_frame.shape[0]/max_height > 1):
        frame_BGR_res = transform.pyramid_reduce(bgr_frame, sigma = 0,
                                                 downscale = bgr_frame.shape[0]/max_height)
    else:
        frame_BGR_res = bgr_frame 
    frame_thermal_res = transform.pyramid_expand(normalized_thermal/255, sigma = 0,
                                                 upscale = scale_factor_of_thermal)#[:,:,0]
    
    # Calculate the transform matrix. Depth 8 is accurate enough for the task.
    # Increasing does not improve the results, and sometimes makes things
    # worse since the frames are not homogenously informative enough.
    transform_matrix = _calculate_transform_matrix(frame_BGR_res, frame_thermal_res,
                                                   division_depth = 8,
                                                   desired_thermal_scale = 1/scale_factor_of_thermal)

            
    with shared_transform_matrix.get_lock(): 
        shared_transform_matrix[:] = transform_matrix.flatten()
    
    print('************************************')
    print('************************************')
    print('************************************')
    print('************************************')
    print('************************************')
    print('TRANSFORM MATRIX')
    print(transform_matrix)
    print('************************************')
    print('************************************')
    print('************************************')
    print('************************************')
    print('************************************')
    sys.stdout.flush()
    
    

def detect_face_location(bgr_frame, face_detector, faces_queue):
    
    print('thread 3')
    sys.stdout.flush()
    
    rotat = cv2.rotate(bgr_frame, cv2.ROTATE_90_CLOCKWISE)
    faces = face_detector.detectMultiScale(rotat,1.05,1, minSize = (10,10),  maxSize = (150,150))
    #faces = face_detector.detectMultiScale(bgr_frame,1.05,3, minSize = (10,10))

    if not isinstance(faces,tuple):  # if faces are returned

        rotated_back_faces = []
        for x,y,w,h in faces:
            zeros = np.zeros_like(rotat)
            zeros[y,x] = 1
            rotat_zeros = cv2.rotate(zeros, cv2.ROTATE_90_COUNTERCLOCKWISE)
            y_rotat,x_rotat,_ = np.unravel_index(rotat_zeros.argmax(), rotat_zeros.shape)
            rotated_back_faces.append((x_rotat, y_rotat, h, w))
        
        rotated_back_faces = [(x,y,w,h) for x,y,w,h in rotated_back_faces if (180 >= x >= 60) and (135 >= y >= 45)]
        
        if rotated_back_faces:
        
            faces_queue.put(rotated_back_faces)
        
        else:
            
            faces_queue.put(None)
        
    else:
        
        faces_queue.put(None)
        

        
        
