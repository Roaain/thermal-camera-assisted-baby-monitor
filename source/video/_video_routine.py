import sys

from helper_modules.pylepton import Lepton
from video.frame_preprocessing import float_to_uint8

import numpy as np
import cv2
from skimage import transform
import time

import time
import os

class MockLepton:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def capture(self, *args, **kwargs):
        time.sleep(0.1)
        return np.random.randint(7000, 8200, (60, 80), dtype=np.uint16), int(time.time()*1000)

class MockVideoCapture:
    def __init__(self, *args): pass
    def isOpened(self): return True
    def set(self, *args): pass
    def read(self):
        time.sleep(1/30.0)
        return True, np.random.randint(0, 255, (180, 240, 3), dtype=np.uint8)
    def release(self): pass

from queue import Empty

def video_routine(frame_queue, bgr_thermal_queue, aux_temp, temp_dict, shared_transform_matrix,
                  baby_is_crying, faces_queue, baby_temp):

    '''
    Routine that:
        + Acquires BGR and Thermal video frames,
        + Aligns them using the alignment vector provided by the control process,
        + overlaying them according to a predetermined colormap.
    
    It also feeds the frames into the control thread, but this action does not
    take much time (tested) and it doesn't need to be modified in the future.
    
    Beware that this routine takes the initial thermal frame first for better
    alignment, since the rgb is much faster. That is the reason for the thermal 
    capture before the 'while' loop.
    '''
        
    # IMPORTANT CONSTANTS
    RESOLUTION = (240,180) # Beware that this is the inverse of numpy ordering!
    NP_COMPAT_RES = (180,240)
    THERMAL_RES = (60,80)
    #CHIP_DESELECT = 0.185 # Deselect duration after corruption, in milliseconds.
    CHIP_DESELECT = 0.25
    
    # Initialize necessary variables
    transform_matrix = np.array([[ 2.81291628e-11, 1.00000000e+00, -5.06955742e-13,  8.35398829e-16, -1.56637280e-15,  2.92389590e-15],
                                 [-3.00482974e+01, 1.20000000e-01,  1.00000000e+00, -5.00000000e-04, 6.40729980e-16,  6.20157957e-16]])
    transform_obj = transform.PolynomialTransform(transform_matrix)
    
    # Initialize the BGR camera using OpenCV
    bgr_camera = cv2.VideoCapture(0)
    if not bgr_camera.isOpened() or not os.path.exists("/dev/video0"):
        print("Using MockVideoCapture")
        bgr_camera = MockVideoCapture(0)
    bgr_camera.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUTION[0])
    bgr_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
    bgr_camera.set(cv2.CAP_PROP_FPS, 30)
    
    # detected faces initialization
    detected_faces = None
    max_temp = 45
    
    # Initialize the thermal camera, create the handle. 
    # DO NOT FORGET TO CLOSE IT MANUALLY!
    try:
        thermal_camera = Lepton("/dev/spidev0.1")
        with thermal_camera as tcam:
            tcam.capture()
    except Exception:
        print("Using MockLepton")
        thermal_camera = MockLepton()
    
    print('yes')
    sys.stdout.flush()
    
    # Wrap the function into a try/finally block to handle the exit
    try:
        
        # Take the first thermal frame to couple with the first BGR frame.
        # Wait if the frame is bad, until you get a good one.
        # Lepton sometimes return the same frame, so if the frame id is 
        # identical, no processing is necessary.
        # Walrus operator would be so nice to use here...
            
        raw_thermal_frame = False
        while not type(raw_thermal_frame) is np.ndarray:
            time.sleep(CHIP_DESELECT)
            with thermal_camera as tcam:
                raw_thermal_frame, thermal_id = tcam.capture(retry_reset = False,
                                                             return_false_if_error = True)
                print('Waiting for correct frame')
            sys.stdout.flush() 
        
        start_time = time.perf_counter()
        # Flag for the unique thermal frame and corrupted frame.
        # Corrupted frame flag carries a time value to leave
        # the chip deselected for CHIP_DESELECT duration
        thermal_frame_is_unique = True
        thermal_frame_is_corrupted = (False, time.perf_counter())
        
        # Start the loop! 
        # Start the loop! 
        while True:
            ret, frame = bgr_camera.read()
            if not ret:
                print('Failed to read from camera')
                break
            
            # Acquire the BGR frame
            bgr_frame = np.flip(frame, 0).astype(np.uint8)
            #raw_thermal_frame = np.flip(raw_thermal_frame,0)
            rotated_thermal_frame = np.flip(cv2.rotate(raw_thermal_frame, cv2.ROTATE_90_CLOCKWISE),1)
            raw_thermal_frame = np.zeros(THERMAL_RES)
            raw_thermal_frame[:-7,8:-12] = rotated_thermal_frame[27:,:]
            
            #print(raw_thermal_frame)
            #print(raw_thermal_frame.shape)
            #print(raw_thermal_frame.dtype)
            
            # Do the processing if the thermal frame is unique. If not,
            # nothing much to do! 
            # BEWARE THAT raw_thermal_frame IS NOT USABLE! IF YOU WANT TO USE IT,
            # THEN A COPY IS NECESSARY!
            if( thermal_frame_is_unique):
                
                # Put them into the queue
                bgr_thermal_queue.put((bgr_frame, raw_thermal_frame))
                
                # Preprocess the thermal frame to clip the values into some
                # predetermined thresholds
                aux_temperature = aux_temp.value
                    
                # min_thresh = [x[0] for x in temp_dict.items() if x[1] == 32 + temperature_offset][0] # 32 and 42 degrees, respectively
                # max_thresh = [x[0] for x in temp_dict.items() if x[1] == 42 + temperature_offset][0]
                #min_thresh = 7600
                #max_thresh = 8000
                min_thresh = (20 + 322.895 - aux_temperature * 1.2803) / 0.0403 #23 degrees
                max_thresh = (35 + 322.895 - aux_temperature * 1.2803) / 0.0403 #38 degrees
                dummy_added_thermal_frame = raw_thermal_frame.copy()
                dummy_added_thermal_frame[0,1] = min_thresh
                dummy_added_thermal_frame[0,0] = max_thresh
                corrected_thermal_frame = np.clip(dummy_added_thermal_frame, min_thresh, max_thresh)
        
                # Normalize thermal frame to 0-255
                cv2.normalize(corrected_thermal_frame, 
                              corrected_thermal_frame, 0, 255, cv2.NORM_MINMAX)
                
                # Acquire the transform matrix and if it is new, create transform object
                with shared_transform_matrix.get_lock(): 
                    new_transform_matrix = np.array(shared_transform_matrix).reshape((2,6))
                if not np.array_equal(new_transform_matrix, transform_matrix):
                    transform_matrix = new_transform_matrix
                    transform_obj = transform.PolynomialTransform(transform_matrix)
                
                # Warp the thermal image according to the transform object.
                # TODO: Correct the division by 255 thing, it is weird.
                warped_thermal_frame = transform.warp(corrected_thermal_frame.astype(float), transform_obj).astype(np.uint8)
                                
                # Scale the thermal frame to have the same size with the BGR.
                # Pyramid expand method from skimage creates a smoother output,
                # but the the difference in speed is more than 20x. So, we will
                # use this method from cv2.
                scale = NP_COMPAT_RES[0] / THERMAL_RES[0]
                scaled_thermal_frame = cv2.resize(warped_thermal_frame, None,
                                                  fx = scale, fy = scale,
                                                  interpolation = cv2.INTER_LINEAR)
                
                # Apply color map to the scaled frame
                # Beware that the output is also BGR.
                colored_thermal_frame = cv2.applyColorMap(scaled_thermal_frame,
                                                          cv2.COLORMAP_JET)
            
            # Sum the thermal and BGR frames (even if it is not unique)
            overlay = cv2.addWeighted(colored_thermal_frame, 0.25, bgr_frame, 0.75, 0)
            
            # Write temperature on overlay
            #max_temp = temp_dict[int(np.max(raw_thermal_frame))] + temperature_offset
            max_temp = baby_temp.value
            # print('max value: {}'.format(np.max(raw_thermal_frame)))


            if(70 >= max_temp >= 15):
            
                cv2.putText(overlay, 'Temp-in-range: {}'.format(round(max_temp,2)),
                            (10,NP_COMPAT_RES[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.25, (255,255,255), 1)
            
            cv2.putText(overlay, (':(' if baby_is_crying.value else ':)'),
                        (NP_COMPAT_RES[1] - 30, NP_COMPAT_RES[0] - 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255,255,255), 1)
            
            try:
                detected_faces = faces_queue.get( block = False)
            except Empty:
                pass
            
            if( detected_faces is not None):
                for (x,y,w,h) in detected_faces:
                    cv2.rectangle(overlay, (x,y), (x+w,y-h), (255,255,255), 1)
            
            # Video processed!
##            print('Unique frame' if thermal_frame_is_unique else 'Repeating frame')
##            print('FPS: {}'.format(1/(time.perf_counter()- start_time)))
##            sys.stdout.flush()
            print('MAX TEMP: {}'.format(max_temp))
            start_time = time.perf_counter()
            
            # Send the frame to queue
            frame_queue.put(overlay[45:,:]) # cut 45 from above
            
            # Now, get the next thermal frame. First, check if the last thermal 
            # frame was corrupted. If not, just capture as usual.
            if( thermal_frame_is_corrupted[0]): 
                
                # If that is the case, check if CHIP_DESELECT time has passed since
                # the corruption. If so, take a new frame and turn the flag to False.
                # If not, just use the old frames as the new ones. The id's will 
                # be checked to prevent reprocessing in the next if block.
                if(time.perf_counter() - thermal_frame_is_corrupted[1] > CHIP_DESELECT):
                    with thermal_camera as tcam:
                        new_raw_thermal_frame, new_thermal_id = tcam.capture(retry_reset = False,
                                                                                       return_false_if_error = True)
                    thermal_frame_is_corrupted = (False, time.perf_counter())
                
                else:
                    new_raw_thermal_frame, new_thermal_id = raw_thermal_frame, thermal_id
            
            else:
                with thermal_camera as tcam:
                    new_raw_thermal_frame, new_thermal_id = tcam.capture(retry_reset = False,
                                                                                   return_false_if_error = True)
            
            # If the capture was successful or the necessary time for the
            # corruption flag to be removed has not passed, check the uniqueness and 
            # continue. 
            if type(new_raw_thermal_frame) is np.ndarray:
                
                if thermal_id != new_thermal_id:
                    raw_thermal_frame = new_raw_thermal_frame
                    thermal_frame_is_unique = True
                else:
                    thermal_frame_is_unique = False
            
            # If the frame was corrupted, just use the old frames and set the 
            # corruption flag.
            else:
                thermal_frame_is_unique = False
                thermal_frame_is_corrupted = (True, time.perf_counter())
            
    finally:
        
        bgr_camera.release()
        print('video routine stopped.')
        sys.stdout.flush()