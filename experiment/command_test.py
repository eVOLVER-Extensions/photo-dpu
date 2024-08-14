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

usage = '''
Usage::
\tUse to set a parameter on all vials to one value:
\t python3 command_test.py <parameter> <value>
\t python3 command_test.py light 0


\tUse to set a parameter on values on individual vials:
\t python3 command_test.py <parameter> <value_array>

\tFor temperature, a 16-value list:
\t python3 command_test.py temp 1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500

\tFor light, a 32-value list:
\t python3 command_test.py light 0,2100,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
\t light1 (white) = first 16 values | light2 (unused) = second 16 values

'''

class EvolverNamespace(BaseNamespace):
    def on_connect(self, *args):
        print("Connected to eVOLVER as client")

    def on_disconnect(self, *args):
        print("Discconected from eVOLVER as client")

    def on_reconnect(self, *args):
        print("Reconnected to eVOLVER as client")

    def on_broadcast(self, data):
        print(data)       

def run_test(time_to_wait, selection):
	time.sleep(time_to_wait)
	print('Sending data...')

	# Send temp	
	if type(value) == int:
		if parameter == 'light':
			data = {'param': parameter, 'value': [value] * 32, 'immediate': True}
		else:
			data = {'param': parameter, 'value': [value] * 16, 'immediate': True}
	
	else: # "value" is already a list 
		data = {'param': parameter, 'value': value, 'immediate': True}
	
	print(data)
	evolver_ns.emit('command', data, namespace = '/dpu-evolver')

def start_background_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

def run_client():
	global evolver_ns, socketIO
	socketIO = SocketIO(EVOLVER_IP, EVOLVER_PORT)
	evolver_ns = socketIO.define(EvolverNamespace, '/dpu-evolver')
	socketIO.wait()

if __name__ == '__main__':
	global parameter
	global value
	try:
		parameter = str(sys.argv[1])
	except:
		print('Error: parameter entered incorrectly')
		sys.exit()

	try:
		value = int(sys.argv[2])

	except:
		print(sys.argv[2])
		value = sys.argv[2].split(",")

		print("Value array is length " + str(len(value)))

		if parameter == 'light' and len(value) != 32:
			print("Error: LIGHT Value array is length " + str(len(value)) + "; array should be length 32")
			print(usage)
			sys.exit()

		elif parameter == 'pump' and len(value) != 48:
			print("Error: PUMP Value array is length " + str(len(value)) + "; array should be length 48")
			print(usage)
			sys.exit()

		# elif len(value) != 16:
		# 	print("Error: Value array is length " + str(len(value)) + "; array should be length 16")
		# 	print(usage)
		# 	sys.exit()
	try:
		new_loop = asyncio.new_event_loop()
		t = Thread(target = start_background_loop, args = (new_loop,))
		t.daemon = True
		t.start()
		new_loop.call_soon_threadsafe(run_client)
		time.sleep(5)
		run_test(0, 0)
	except KeyboardInterrupt:
		socketIO.disconnect()
