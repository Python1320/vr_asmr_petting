import asyncio
import os
import sys
import time
from typing import Awaitable
from psutil import process_iter

import ctypes
import traceback
import logging

from pathlib import Path

from aiohttp import web
from zeroconf.asyncio import AsyncZeroconf
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.dispatcher import Dispatcher
from vrchat_oscquery.common import _unused_port, _oscjson_response, _create_service_info, _get_app_host


import tkinter as tk
import tkinter.ttk as ttk
import webbrowser
from asyncio import Future

import openvr
import openvr.error_code
# import audio_visualization
# audio_visualization.init()


HELP_URL = 'https://github.com/Python1320/vr_asmr_petting?tab=readme-ov-file#help'

FROZEN = getattr(sys, 'frozen', False)
DEBUGGER = 'debugpy' in sys.modules
EXEDIR = Path(sys.prefix) if FROZEN else Path(__file__).parent
# print(Path(__file__).parent, Path(sys.prefix), EXEDIR)


def show_console():
	ctypes.windll.kernel32.AllocConsole()
	sys.stdout = open('CONOUT$', 'wt')
	sys.stderr = open('CONOUT$', 'wt')


def is_vrchat_running() -> bool:
	_proc_name = 'VRChat.exe' if os.name == 'nt' else 'VRChat'
	return _proc_name in (p.name() for p in process_iter())


def fatal(msg, detail=None, nodecor=False):
	if 'debugpy' in sys.modules:
		raise  # Exception(str(msg))

	# if os.name == 'nt':
	# ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), 'vr_asmr_petting - ERROR', 0)
	# else:
	# print(msg)

	title = 'VR Audience Fire: Error'
	message = str(msg) if nodecor else 'An error has occured, sorry about that.\n\nDetails: ' + str(msg)
	detail = detail or traceback.format_exc()
	TopErrorWindow(title, message, detail)

	logging.error(traceback.format_exc())
	exit()


def handle_errors(task):
	try:
		exc = task.exception()
		if exc:
			traceback.print_exception(type(exc), exc, exc.__traceback__)
	except asyncio.exceptions.CancelledError:
		pass


all_tasks = []


def task_done(task):
	all_tasks.remove(task)
	handle_errors(task)


def spawn_task(awaitable, loop=None):
	loop = loop or asyncio.get_running_loop()
	task = loop.create_task(awaitable)
	all_tasks.append(task)
	task.add_done_callback(task_done)
	return task


def exit(n=1):
	if n != 0:
		logging.error('Exiting forcefully...')
	else:
		logging.info('Exiting gracefully...')
	os._exit(n)


class TopErrorWindow(tk.Tk):
	def __init__(self, title, message, detail):
		super().__init__()
		self.details_expanded = True
		self.title(title)
		self.geometry('600x450')
		self.minsize(600, 450)
		self.resizable(True, True)
		self.rowconfigure(0, weight=0)
		self.rowconfigure(1, weight=1)
		self.columnconfigure(0, weight=1)

		button_frame = tk.Frame(self)
		button_frame.grid(row=0, column=0, sticky='nsew')
		button_frame.columnconfigure(0, weight=1)
		button_frame.columnconfigure(1, weight=1)

		text_frame = tk.Frame(self)
		text_frame.grid(row=1, column=0, padx=(7, 7), pady=(7, 7), sticky='nsew')
		text_frame.rowconfigure(0, weight=1)
		text_frame.columnconfigure(0, weight=1)

		txt = tk.Text(button_frame, height=1, borderwidth=0)
		txt.grid(row=0, column=0, columnspan=3, pady=(7, 7), padx=(7, 7), sticky='w')
		txt.insert('1.0', message)

		ttk.Button(button_frame, text='Exit', command=self.destroy).grid(row=1, column=1, sticky='e')

		ttk.Button(
			button_frame,
			text='Help',
			command=lambda: webbrowser.open_new_tab(HELP_URL),
		).grid(row=1, column=2, padx=(7, 7), sticky='e')

		self.textbox = tk.Text(text_frame, height=6)
		self.textbox.insert('1.0', detail)
		self.textbox.config(state='disabled')
		self.scrollb = tk.Scrollbar(text_frame, command=self.textbox.yview)
		self.textbox.config(yscrollcommand=self.scrollb.set)
		self.textbox.grid(row=0, column=0, sticky='nsew')
		self.scrollb.grid(row=0, column=1, sticky='nsew')
		self.mainloop()


class VRCOSCClient:
	osc_port: int = -1
	osc_host: str = ''
	http_port: int = -1

	def __init__(self, osc_port: int = -1, osc_host: str = '', http_port: int = -1):
		self.osc_host = osc_host
		self.osc_port = osc_port
		self.http_port = http_port


# Custom version of vrc_osc with VRC bugfix and returning params
async def vrc_osc(name: str, dispatcher: Dispatcher, foreground=False, zeroconf=True):
	osc_port = _unused_port()
	http_port = _unused_port()
	host = _get_app_host()

	await AsyncIOOSCUDPServer((host, osc_port), dispatcher, asyncio.get_event_loop()).create_serve_endpoint()  # type: ignore
	if zeroconf:
		app = web.Application()
		last_root_requested = time.monotonic() + 5
		last_hinfo_requested = time.monotonic() + 5

		def req_handler(req):
			nonlocal last_root_requested, last_hinfo_requested
			request_path = req.path_qs
			if request_path == '/':
				if time.monotonic() - last_root_requested < 1:
					logging.debug('BUGFIX: Too many requests to root path, throttling due to BUG.')
					return web.Response(status=404, body='Too many requests, please wait a moment.')
				last_root_requested = time.monotonic()
			elif request_path == '/?HOST_INFO':
				if time.monotonic() - last_hinfo_requested < 1:
					logging.debug('BUGFIX: Too many requests to HOST_INFO, throttling due to BUG.')
					return web.Response(status=404, body='Too many requests, please wait a moment.')
				last_hinfo_requested = time.monotonic()

			return web.Response(body=_oscjson_response(req.path_qs, osc_port))

		app.add_routes([web.get('/', req_handler)])  # type: ignore
		runner = web.AppRunner(app)
		await runner.setup()
		await web.TCPSite(runner, host, http_port).start()

		await AsyncZeroconf().async_register_service(_create_service_info(name, http_port))

	if foreground:
		await asyncio.gather(*asyncio.all_tasks())

	client = VRCOSCClient(osc_port=osc_port, osc_host=host, http_port=http_port)
	return client


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
	except openvr.error_code.TrackedProp_InvalidDevice as e:
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
	send_untap = None
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


vr_system_fut: Future[openvr.IVRSystem]


async def _get_vr_system(app_type=openvr.VRApplication_Overlay):
	if not vr_system_fut:
		raise RuntimeError('Future not initialized')

	if vr_system_fut.done():
		raise RuntimeError('VR System already initialized')
	init_errored = False
	for i in range(999999):
		try:
			vr_system = openvr.init(app_type)
			vr_system_fut.set_result(vr_system)
			logging.info('OpenVR initialized successfully')
			break
		except openvr.error_code.InitError_Init_VRClientDLLNotFound:
			raise
		except openvr.error_code.InitError_Init_NoServerForBackgroundApp:
			if not init_errored:
				init_errored = True
				print('Waiting for SteamVR...')
		except Exception as e:
			fatal(f'Failed to initialize OpenVR: {e}')
		await asyncio.sleep(2.1)


vr_system_first = True


async def get_vr_system(
	app_type=openvr.VRApplication_Overlay, loop: asyncio.AbstractEventLoop | None = None
) -> openvr.IVRSystem:
	global vr_system_first, vr_system_fut
	if vr_system_first:
		vr_system_first = False
		assert loop is not None, 'Loop must be provided on first call'
		vr_system_fut = Future(loop=loop)
		spawn_task(_get_vr_system(app_type))
	await vr_system_fut
	return vr_system_fut.result()


if __name__ == '__main__':
	show_console()
	logging.error('This is a utility module, not meant to be run directly.')
	print('Please run the main script instead.')
	TopErrorWindow('test title', 'test message', """These are some details\nnewline\nmore details""")
	input('Press Enter to exit...')


def set_console_title(title: str):
	if os.name == 'nt':
		ctypes.windll.kernel32.SetConsoleTitleW(title)
	else:
		print(f'\033]0;{title}\a', end='', flush=True)
