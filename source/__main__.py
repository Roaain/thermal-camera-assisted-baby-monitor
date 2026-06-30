from multiprocessing import Process, Value, Array
from helper_modules.continuous_queue import ContinuousQueue as Queue

from ctypes import c_bool
# from pexpect import pxssh
import sys
import numpy as np

from audio._audio_routine import audio_routine
from video._video_routine import video_routine
from server._server_routine import server_routine
from control._control_routine import control_routine

from scipy.io import loadmat

# BEWARE! This code cannot be run from an IDE, as using an editor such as IPython
# prevents multiprocessing. Use command prompt or a similar environment, or run
# directly by python.exe

if __name__ == '__main__':
    
    # Initialize queues. Frame and Audio queues are connected to server process,
    # but rgb and thermal frames are also fed into to control process via 
    # rgb_thermal_queue
    bgr_thermal_queue = Queue(2)
    frame_queue = Queue(5)
    audio_queue = Queue(10)
    faces_queue = Queue(1)
    
    # Initialize transform matrix, a shared memory for video and control processes.
    # NOTE TO SELF: give a sensible transform matrix for the initial case
    shared_transform_matrix = Array('d', [ 9.37830895e-12,   1.00000000e+00,  -3.96434172e-13,
                                           8.62639189e-16,   2.35265233e-16,   5.09741339e-15,
                                          -1.11682496e+01,  -9.00591808e-03,   1.00000000e+00,
                                           6.29504763e-04,   7.57604597e-17,  -1.65846804e-15])
    
    # Initialize shared memories for value types.
    room_temp = Value('f', 23.5)
    room_humid = Value('f', 36.09)
    baby_temp = Value('f', 0.0)
    baby_is_crying = Value(c_bool, False)
    baby_feverish = Value(c_bool, False)
    temp_offset = Value('f', 3.0)
    
    # Load temperature map
    import os
    temp_table_path = os.path.join(os.path.dirname(__file__), 'control', 'temp_map_piecewise_linear.mat')
    temp_table = loadmat(temp_table_path)['temp_v2']
    temp_table = np.hstack((temp_table[4001:],temp_table[:4001]))
    temp_dict = {int(a):b for a,b in temp_table}
    
    # Initialize Process objects and target the necessary routines
    audio_process = Process(name = 'audio_process',
                            target=audio_routine, args=(audio_queue, baby_is_crying))
    video_process = Process(name = 'video_process',
                            target=video_routine, args=(frame_queue, bgr_thermal_queue,
                                                        temp_offset, temp_dict,
                                                        shared_transform_matrix, baby_is_crying,
                                                        faces_queue, baby_temp))
    server_process = Process(name = 'server_process',
                             target=server_routine, args=(frame_queue, audio_queue,
                                                          room_temp, room_humid, baby_temp,
                                                          baby_is_crying,baby_feverish))
    control_process = Process(name = 'control_process',
                              target=control_routine, args=(bgr_thermal_queue,
                                                            shared_transform_matrix,
                                                            room_temp, room_humid, baby_temp, temp_offset,
                                                            temp_dict, faces_queue, baby_feverish))
    
    # Start the processes.
    video_process.start()
    audio_process.start()
    control_process.start()
    server_process.start()


