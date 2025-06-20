import sys, math, time
import openvr
import wave
import sys
#import audio_visualization
#audio_visualization.init()


try:
	from pythonosc.udp_client import SimpleUDPClient

except ModuleNotFoundError as e:
	try:
		import subprocess, sys
		print("Trying to install required dependencies...")
		subprocess.check_call(
		    [sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'])
		subprocess.check_call(
		    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
		print("Please restart the program...")
		input()
		import sys
		sys.exit(1)
	except Exception as e:
		print("Something failed big time...")
		print(e)
		input()
		

def get_controller_ids(vrsys=None):
	if vrsys is None:
		vrsys = openvr.VRSystem()
	else:
		vrsys = vrsys
	left = None
	right = None
	for i in range(openvr.k_unMaxTrackedDeviceCount):
		device_class = vrsys.getTrackedDeviceClass(i)
		if device_class == openvr.TrackedDeviceClass_Controller:
			role = vrsys.getControllerRoleForTrackedDeviceIndex(i)
			if role == openvr.TrackedControllerRole_RightHand:
				right = i
			if role == openvr.TrackedControllerRole_LeftHand:
				left = i
	return left, right


def getDeviceIDbySerial(serial_want,vr_system):
	if type(serial_want)==int:
		return serial_want
		
	try:
		for i in range(openvr.k_unMaxTrackedDeviceCount):
			serial = vr_system.getStringTrackedDeviceProperty(
				i,
				openvr.Prop_SerialNumber_String,
			)
			if serial == serial_want:
				return i
	except openvr.error_code.TrackedProp_InvalidDevice as e:
		print("ERROR FINDING",serial_want,": TrackedProp_InvalidDevice")
		return False

def dump_devices(vr_system):
	print("Devices:")
	for i in range(openvr.k_unMaxTrackedDeviceCount):
		try:
			serial = vr_system.getStringTrackedDeviceProperty(
			    i, openvr.Prop_SerialNumber_String)
		except openvr.error_code.TrackedProp_InvalidDevice:
			continue

		dclass = vr_system.getInt32TrackedDeviceProperty(
		    i, openvr.Prop_DeviceClass_Int32)
		if dclass != openvr.k_unTrackedDeviceIndexInvalid:
			print(" - ", serial, dclass)



class TrackConfig:
	name = None
	osc_message = None
	osc_tap_message = None
	serial = None
	device_id = None
	delta = None
	tapped = None
	send_untap=None
	
	def __init__(self, name=None, osc_message=None, osc_tap_message=None, serial=None,oscClient=None):
		self.name = name
		self.osc_message = osc_message
		self.osc_tap_message = osc_tap_message
		self.serial = serial
		self.device_id = None
		self.delta = [0,0]
		self.tapped = None
		self.send_untap=False
		self.oscClient=oscClient
	def attempt_tracking(self):
		todo()
		pass
	def set_tap_telemetry(self,f):
		self.oscClient.send_message(self.osc_tap_message, f)
	def set_telemetry(self,f):
		self.oscClient.send_message(self.osc_message, f)
		
		

def wait_controllers(vrsystem):

	left_id, right_id = None, None
	printed = False
	try:
		while left_id is None or right_id is None:
			left_id, right_id = get_controller_ids(vrsystem)
			if left_id and right_id:
				print("GOT:",(left_id, right_id))
				return (left_id, right_id)
			printed = printed or print(
			    "Waiting for controllers (Press ctrl+c to quit)...") or True
			time.sleep(1.1)
	except KeyboardInterrupt:
		openvr.shutdown()
