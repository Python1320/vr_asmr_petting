import logging
import asyncio
import os
import sys

# vrchat_oscquery provides zeroconf
import coloredlogs
from pythonosc.dispatcher import Dispatcher
import asmr_worker
from vrchat_oscquery.common import vrc_client

import openvr
import openvr.error_code
import config_reader
from utils import fatal, exit as _exit, spawn_task, FROZEN, EXEDIR, DEBUGGER, show_console, vrc_osc, get_vr_system

print('VR ASMR Petting starting...')


NAME = 'vr_asmr_petting'
LOGFILE = EXEDIR / 'debug.log'
HAS_TTY = sys.stdout and sys.stdout.isatty()
if HAS_TTY:
	coloredlogs.install(level='DEBUG', fmt='%(asctime)s %(name)s %(levelname)s %(message)s')
log = logging.getLogger(name=NAME)

fileHandler = logging.FileHandler(LOGFILE, mode='w')
logFormatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s')
fileHandler.setFormatter(logFormatter)
log.addHandler(fileHandler)

log.debug('Logging to %s', LOGFILE)

conf = config_reader.get_config()


if conf.debug and os.name == 'nt' and not HAS_TTY:
	show_console()
	logging.basicConfig(level=logging.DEBUG)


def exit(n=0):
	_exit(n)


log.info(f'EXEDIR: {EXEDIR}')
log.info(f'FROZEN: {FROZEN}')
log.info(f'DEBUGGER: {DEBUGGER}')


main_loop = asyncio.new_event_loop()  # type: ignore
main_loop.set_debug(True)
vrc = vrc_client()


AVATAR_CHANGE_PARAMETER = '/avatar/change'


async def reg_openvr():
	log.info('Registering OpenVR autostart...')
	global overlay
	try:
		_vr_system = await get_vr_system(openvr.VRApplication_Overlay, loop=main_loop)

		log.debug('notification test')
		overlay = openvr.IVROverlay()
		notification = openvr.IVRNotifications()
		log.info(
			'Installing to SteamVR: %s %s',
			EXEDIR / 'app.vrmanifest',
			openvr.VRApplications().addApplicationManifest(str((EXEDIR / 'app.vrmanifest').resolve())),
		)

		try:
			openvr.IVRNotifications.createNotification(
				notification,
				overlay.createOverlay(overlayKey='vraf', overlayName=''),
				0,
				openvr.EVRNotificationType_Transient,
				'VR Audience Fire Starting',
				openvr.EVRNotificationStyle_Application,
				None,
			)
		except openvr.error_code.NotificationError_OK:  # why would this throw an error
			pass
		except openvr.error_code.NotificationError as e:
			log.error(f'NotificationError: {e}')
			if DEBUGGER:
				raise

	except Exception as e:
		fatal(str(e))


asmr_worker_routine = None


async def init_main():
	global disp, vrc, osc_receiver, osc_server, qclient, transport, protocol, main_loop, asmr_worker_routine

	def avatar_change(addr, value):
		log.info(f'Avatar changed/reset {addr} {value}...')
		# spawn_task(audience_fire.on_reset())

	try:
		disp = Dispatcher()

		disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)

		def wrap_into_async_osc_bool(cb):
			def _wrapper(key, *val):
				# log.debug(f'{key} {val}')
				# TODO: queue?
				spawn_task(cb(bool(val[0])))

			return _wrapper

		detection_map = {
			#'bullet': audience_fire.on_water,
		}
		osc_detectors = conf.osc_detectors or {}
		for key, cb in detection_map.items():
			detector_path = osc_detectors.get(key, None)
			if detector_path:
				disp.map(detector_path, wrap_into_async_osc_bool(cb))
			else:
				log.warning(f'No OSC avatar parameter path for "{key}" found in config, {key} will not work')
		# disp.set_default_handler(asdqwe)

		server_details = await vrc_osc(NAME, disp, zeroconf=conf.zeroconf)
		log.info(
			f'Server started: http://{server_details.osc_host}:{server_details.http_port} osc_port={server_details.osc_port}'
		)
		log.info(
			f'Example: sendosc {server_details.osc_host} {server_details.osc_port} {osc_detectors.get("bullet", "/avatar/parameters/???")} b true'
		)

		asmr_worker_routine = spawn_task(asmr_worker.start(vrc, await get_vr_system(openvr.VRApplication_Overlay)))

		try:
			while True:
				sys.stdout.write('.')
				sys.stdout.flush()
				await asyncio.sleep(7)
		except asyncio.exceptions.CancelledError:
			pass
		# https://docs.python.org/3/library/asyncio-task.html#task-cancellation

	except OSError as e:
		if DEBUGGER:
			raise
		else:
			fatal(str(e))
	except KeyboardInterrupt:
		exit()
	except Exception as e:
		if DEBUGGER:
			raise
		else:
			fatal(str(e))


if __name__ == '__main__':
	if conf.install_to_steamvr:
		main_loop.run_until_complete(reg_openvr())
	print('finished registration, starting main loop...')
	main_loop.run_until_complete(init_main())
