import asyncio
import sys


from pathlib import Path

from pythonosc.udp_client import SimpleUDPClient


import openvr
import openvr.error_code

# import audio_visualization
# audio_visualization.init()


FROZEN = getattr(sys, 'frozen', False)
DEBUGGER = 'debugpy' in sys.modules
EXEDIR = Path(sys.prefix) if FROZEN else Path(__file__).parent
# print(Path(__file__).parent, Path(sys.prefix), EXEDIR)


def find_asset(filename: str) -> Path | None:
	"""Gotta find it somewhere eventually"""
	search_paths = [
		EXEDIR / 'assets' / filename,
		EXEDIR / filename,
		Path('assets') / filename,
		EXEDIR / 'src' / 'assets' / filename,
		Path('src') / 'assets' / filename,
		Path(filename),
	]

	for path in search_paths:
		if path.exists():
			return path.resolve()

	return None


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


def getDeviceIDbySerial(serial_want: int | str, vr_system) -> int | bool | None:
	if type(serial_want) is int:
		return serial_want

	try:
		for i in range(openvr.k_unMaxTrackedDeviceCount):
			serial = vr_system.getStringTrackedDeviceProperty(
				i,
				openvr.Prop_SerialNumber_String,
			)
			if serial == serial_want:
				return i
	except openvr.error_code.TrackedProp_InvalidDevice:
		print('ERROR FINDING', serial_want, ': TrackedProp_InvalidDevice')
		return False


def dump_devices(vr_system):
	print('Devices:')
	for i in range(openvr.k_unMaxTrackedDeviceCount):
		try:
			serial = vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
		except openvr.error_code.TrackedProp_InvalidDevice:
			continue

		dclass = vr_system.getInt32TrackedDeviceProperty(i, openvr.Prop_DeviceClass_Int32)
		if dclass != openvr.k_unTrackedDeviceIndexInvalid:
			print(' - ', serial, dclass)


class TrackConfig:
	name: str
	osc_message: str
	osc_tap_message: str
	serial: str | None
	device_id: int = -9999
	delta: list[int | float] = [0, 0]
	tapped: bool | None = None
	send_untap: float = 0
	oscClient: SimpleUDPClient

	def __init__(
		self, name: str, osc_message: str, osc_tap_message: str, serial: str | None, oscClient: SimpleUDPClient
	):
		self.name = name
		self.osc_message = osc_message
		self.osc_tap_message = osc_tap_message
		self.serial = serial
		self.device_id = None  # type: ignore
		self.delta = [0, 0]
		self.tapped = None
		self.send_untap = False
		self.oscClient = oscClient
		# Tracks whether this device has been seen in a good (connected + valid) state
		self.was_okay = False
		self.last_raw_speed = 0.0
		# When enabled while already moving, suppress sound until movement nears zero
		self.suppress_until_zero = False
		# Fade-out on touch release: epoch seconds until which we should fade
		self.touch_fade_until = 0.0
		# The telemetry value last sent for this track
		self.last_sent_speed = 0.0
		# Speed value at the moment touch-release fade started; fades should not rise above this
		self.touch_fade_start_value = 0.0
		# Fade-in on touch acquire: epoch seconds until which we should fade in
		self.touch_fade_in_until = 0.0
		# Speed value at the moment touch-acquire fade started; fade-in rises from here to raw_speed
		self.touch_fade_in_start_value = 0.0

	def attempt_tracking(self):
		raise NotImplementedError('TODO')

	def set_tap_telemetry(self, f):
		f = True if f >= 1 else False
		# print('tap', self.osc_tap_message, f, self.oscClient._address, self.oscClient._port)
		self.oscClient.send_message(self.osc_tap_message, f)

	def set_telemetry(self, f):
		self.oscClient.send_message(self.osc_message, f)


async def wait_controllers(vrsystem) -> tuple[int, int] | None:
	left_id, right_id = None, None
	printed = False
	try:
		while left_id is None or right_id is None:
			left_id, right_id = get_controller_ids(vrsystem)
			if left_id and right_id:
				print('GOT:', (left_id, right_id))
				return (left_id, right_id)
			printed = printed or print('Waiting for controllers...') or True
			await asyncio.sleep(1.1)
	except KeyboardInterrupt:
		openvr.shutdown()
