import pyaudio
import wave
import os
import numpy as np
import audioop
import sys
import math
from collections import deque
import time
import socket
import io
import struct
from threading import Timer

class MockAudioStream:
    def __init__(self): pass
    def read(self, chunk, exception_on_overflow=False):
        time.sleep(chunk/48000.0)
        return b'\x00' * (chunk * 4)
    def write(self, data): pass
    def stop_stream(self): pass
    def close(self): pass

class MockSocket:
    def recv(self, n):
        time.sleep(1)
        return b'w'
    def send(self, data): pass
    def makefile(self, mode):
        return io.BytesIO()
    def close(self): pass

def audio_routine(audio_queue, baby_is_crying):
    
    '''
    Routine that:
        + Acquires the audio feed
        + Determines if the baby is crying
    
    Some more features may be added to this routine, so do not overpopulate it 
    just because it looks empty.
    '''
    
    CHUNK = 4096
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    dev_index = 2
    RATE = 48000
    audio = pyaudio.PyAudio()
    audio_lullaby = pyaudio.PyAudio()
    lullaby = wave.open(os.path.join(os.path.dirname(__file__), 'Baby-sleep-music.wav'), 'rb')
    
    rms_deque = deque([0]*8, 8)
    
    cry_timer = time.perf_counter()
    CRYING_LIMIT = 5
    baby_is_crying.value = False
    
    want_image = b'w'
    send_image = b's'

    # Connect a client socket to my_server:8000 (change my_server to the
    # hostname of your server)
    client_socket = socket.socket()
    #client_socket.connect(('188.166.17.65', 3000))
    try:
        client_socket.connect(('167.99.215.27', 3000))
    except Exception:
        print("Using MockSocket")
        client_socket = MockSocket()

    # Make a file-like object out of the connection
    connection = client_socket.makefile('wb')

    answer = client_socket.recv(128)
    while answer != want_image:
        answer = client_socket.recv(128)
        print(answer)

    client_socket.send(send_image)
    
    data_send_thread = None
    data_send_start = 0
    
    try:
        
        server_stream = io.BytesIO()
        try:
            audio_stream = audio.open(format=FORMAT,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input_device_index = dev_index,
                                      input=True,
                                      frames_per_buffer=CHUNK)
        except Exception:
            print("Using MockAudioStream for input")
            audio_stream = MockAudioStream()
        
        try:
            audio_stream_lullaby = audio_lullaby.open(format =audio_lullaby.get_format_from_width(lullaby.getsampwidth()),
                                          channels = lullaby.getnchannels(),
                                          rate = 48000,
                                          output = True)
        except Exception:
            print("Using MockAudioStream for output")
            audio_stream_lullaby = MockAudioStream()

        while True:
            
            # Read data
            data = audio_stream.read(CHUNK ,exception_on_overflow = False)
            
            ######################################################
            ############ Send the data to the server #############
            ######################################################
            
            rms = 20 * math.log10(audioop.rms(data, 2))
            rms_deque.append(rms)
            
            mean_rms = np.mean(np.array(rms_deque))
            
            print('Averaged RMS: {}'.format(mean_rms))
            sys.stdout.flush()
            
            peak_count = np.count_nonzero( np.array(rms_deque) > 50)
            
            if( peak_count > 4):
                baby_is_crying.value = True
                print('BABY CRYING!')
                sys.stdout.flush()
                cry_timer = time.perf_counter()
            elif (time.perf_counter() - cry_timer > CRYING_LIMIT):
                baby_is_crying.value = False
            

            try:
                
                ######################################################
                ############ Send the data to the server #############
                ######################################################
                
                if baby_is_crying.value:
                    lull_data = lullaby.readframes(CHUNK)
                    audio_stream_lullaby.write(lull_data)
                    if(lull_data == ''):
                        lullaby.rewind()
                
                server_stream.write(data)
                # Write the length of the capture to the stream and flush to
                # ensure it actually gets sent
                connection.write(struct.pack('<L', server_stream.tell()))
                connection.flush()
                # Rewind the stream and send the image data over the wire
                server_stream.seek(0)
                connection.write(server_stream.read())
                # Reset the stream for the next capture
                server_stream.seek(0)
                server_stream.truncate()
                
            except KeyboardInterrupt:
                raise RuntimeError
            
            except:
                print('Exception on Audio server')
                sys.stdout.flush()
    
    finally:
        
        lullaby.close()
        audio_stream.stop_stream()
        audio_stream.close()
        audio_stream_lullaby.stop_stream()
        audio_stream_lullaby.close()
        audio.terminate()
        audio_lullaby.terminate()
        connection.close()
        client_socket.close()
        
