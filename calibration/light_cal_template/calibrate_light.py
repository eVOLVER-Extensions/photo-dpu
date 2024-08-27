import socket
from socketIO_client import SocketIO, BaseNamespace
import asyncio
from threading import Thread
import random
import time
import sys

EVOLVER_IP = '192.168.1.6'
EVOLVER_PORT = 8081
evolver_ns = None
socketIO = None

# Light Variables
calibration_vals = [2080,2100,2200,2400,3000,3500,4000,4095]
time_on = 10 # seconds; time to keep the light at a particular value
time_off = 5 # seconds; time to wait after turning the light off (to separate ON vals)

usage = '''

=====================PROGRAM USAGE=====================
Purpose:
	Calibrate a single vial at a time using the LI-1500 probe

Command:
	python3 light_cal.py <vial_num>
Example:
	python3 light_cal.py 5

Check readme.md for protocol

=======================================================

'''

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        print("Connected to eVOLVER as client")

    def on_disconnect(self, *args):
        print("Discconected from eVOLVER as client")

    def on_reconnect(self, *args):
        print("Reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        print("\nData from min-eVOLVER:\n",data)

def run_light_cal(time_to_wait, vial_num, time_on, time_off):
	time.sleep(time_to_wait)
	print(usage)
	print(f'\n\nSending light values to vial {vial_num}...')

	light_list = [0]*32 # initialize list
	# Turn off light to separate in light logger
	data = {'param': 'light', 'value': [0]*32, 'immediate': True}
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')
	print(data)
	time.sleep(time_off)

	for val in calibration_vals:
		light_list[vial_num] = val # set the correct index for this vial to val

		# Set light to value
		print(f'\nLight Val = {val}')
		data = {'param': 'light', 'value': light_list, 'immediate': True}
		evolver_ns.emit('command', data, namespace = '/dpu-evolver')
		print(data)
		time.sleep(time_on) # Wait for data to come in

		# Turn off light to separate in light logger
		data = {'param': 'light', 'value': [0]*32, 'immediate': True}
		evolver_ns.emit('command', data, namespace = '/dpu-evolver')
		print(data)
		time.sleep(time_off)

	print('\nLIGHT CAL COMPLETE\n')

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run_client():
	global evolver_ns, socketIO
	socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
	evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
	socketIO.wait()

if __name__ == '__main__':
	try:
		vial_num = int(sys.argv[1])

	except:
		print(usage)
		sys.exit()

	try:
		new_loop = asyncio.new_event_loop()
		t = Thread(target = start_background_loop, args = (new_loop,))
		t.daemon = True
		t.start()
		new_loop.call_soon_threadsafe(run_client)
		time.sleep(5)
		run_light_cal(0, vial_num, time_on, time_off)
	except KeyboardInterrupt:
		socketIO.disconnect()