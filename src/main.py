import logging
import asyncio
import os
import sys
import json

# vrchat_oscquery provides zeroconf
import coloredlogs
from vrappcommon.AsyncOSCDispatcher import AsyncOSCDispatcher
import asmr_worker
from vrappcommon import openvrutils
from vrappcommon.jankyguihelpers import fatal, show_console
import vrappcommon.jankyguihelpers as gui

from vrappcommon.openvrutils import get_vr_system
from vrappcommon.task_helper import spawn_task
from vrappcommon.jankyguihelpers import ensure_single_instance_app
from vrappcommon.vrutils import vrc_osc
from vrchat_oscquery.common import vrc_client
import vrchat_oscquery.common
import pluginhelper
import openvr
import openvr.error_code
import config_reader
import openvr_actions
from utils import (
	FROZEN,
	EXEDIR,
	DEBUGGER,
)
import importlib
import pkgutil

NAME = 'vr_asmr_petting'
IDENTITY = f'python1320.{NAME}'
APPNAME = 'VR ASMR Petting'
HELP_URL = 'https://github.com/Python1320/vr_asmr_petting?tab=readme-ov-file#help'

gui.set_help_url(HELP_URL)
gui.set_program_name(APPNAME)
gui.set_console_title(APPNAME)
openvrutils.set_identity(IDENTITY)

# === Logging madness ====
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

# === Load configuration, singleton handling ===
conf = config_reader.get_config()


ensure_single_instance_app(NAME)

conf.run_count = (conf.run_count or 0) + 1
asmr_worker.worker.tapping_enabled = bool(conf.autotapping_enabled)
asmr_worker.worker.autopet_on_detect = bool(conf.autopet_on_detect)
asmr_worker.worker.autopet_osc_path = conf.autopet_osc_path
asmr_worker.worker.arm_on_touch = bool(conf.arm_on_touch)
asmr_worker.worker.petting_sound_enable_move_threshold = float(conf.petting_sound_enable_move_threshold or 0.0)
asmr_worker.worker.petting_sound_touch_fade_seconds = float(conf.petting_sound_touch_fade_seconds or 0.5)
config_reader.save_config(conf)

if conf.debug and os.name == 'nt' and not HAS_TTY:
	show_console()
	logging.basicConfig(level=logging.DEBUG, force=True)


if conf.debug_audio_visualization:
	asmr_worker.audio_visualization.init()

if conf.vrc_osc_ip:
	vrchat_oscquery.common.APP_HOST = conf.vrc_osc_ip
	vrchat_oscquery.common.VRC_HOST = conf.vrc_osc_ip
if conf.vrc_osc_port:
	vrchat_oscquery.common.VRC_PORT = conf.vrc_osc_port


log.info(f'EXEDIR: {EXEDIR}')
log.info(f'FROZEN: {FROZEN}')
log.info(f'DEBUGGER: {DEBUGGER}')


main_loop = False

vrc = vrc_client()
asmr_worker_routine = None
AVATAR_CHANGE_PARAMETER = '/avatar/change'
loaded_plugins: dict[str, pluginhelper.VRPlugin] = {}


async def reg_openvr(task_group: asyncio.TaskGroup | None = None):
	log.info('Registering OpenVR autostart...')
	global _vr_system
	try:
		_vr_system = await get_vr_system(
			openvr.VRApplication_Overlay,
			loop=main_loop,
			task_group=task_group,
		)

		log.info(
			'Installing to SteamVR: %s %s',
			EXEDIR / 'app.vrmanifest',
			openvr.VRApplications().addApplicationManifest(str((EXEDIR / 'app.vrmanifest').resolve()), True),
		)
		print('I AM ', os.getpid(), 'aka', openvr.VRApplications().getApplicationKeyByProcessId(os.getpid()))
		print('ASMR IS', openvr.VRApplications().getApplicationProcessId('python1320.vr_asmr_petting'))
	except Exception as e:
		fatal(str(e))


async def load_plugins(task_group: asyncio.TaskGroup | None = None):
	for finder, name, ispkg in pkgutil.iter_modules():
		if name.startswith('plugin_'):
			if ispkg:
				log.warning(f'Skipping package plugin {name}?')
			else:
				try:
					plugin = importlib.import_module(name)
				except Exception as e:
					log.exception(f'Failed to load plugin {name}: {e}')
					continue

				try:
					if not await plugin.on_load(
						conf=conf,
						vrc=vrc,
						main_loop=main_loop,
						task_group=task_group,
					):
						continue
				except Exception as e:
					log.exception(f'Failed to load plugin {name}: {e}')
					fatal(f'Failed to load plugin {name}: {e}')
					raise

				loaded_plugins[name] = plugin  # type: ignore # TODO: REFACTOR: use classes!!

	log.info('Loaded plugins:')
	for name, plugin in loaded_plugins.items():
		log.info(f' - {name}')


async def init_main(task_group: asyncio.TaskGroup):
	global \
		disp, \
		vrc, \
		osc_receiver, \
		osc_server, \
		qclient, \
		transport, \
		protocol, \
		main_loop, \
		asmr_worker_routine, \
		server_details



	def avatar_change(addr, value):
		log.info(f'Avatar changed/reset {addr} {value}...')

	try:
		disp = AsyncOSCDispatcher()
		await disp.set_task_group(task_group)
		pluginhelper.set_osc_dispatcher(disp)

		disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)

		discarded_msg_count = 0

		def received_first_message_from(address, *args):
			nonlocal discarded_msg_count
			discarded_msg_count += 1
			if discarded_msg_count <= 5:
				log.debug(f'Ignoring unknown OSC message from {address}, payload: {args}')
			else:
				disp.set_default_handler(None)  # type: ignore

		disp.set_default_handler(received_first_message_from, True)

		def wrap_into_async_osc_bool(cb):
			def _wrapper(key, *val):
				# log.debug(f'{key} {val}')
				# TODO: queue?
				spawn_task(
					cb(bool(val[0])),
					loop=task_group,
					name=f'osc_bool_{key}',
				)

			return _wrapper

		detection_map = {
			'enabled': asmr_worker.worker.on_enabled,
			'enabled_alt': asmr_worker.worker.on_enabled_alt,
			'tapping_enabled': asmr_worker.worker.set_tapping_enabled,
			'attacked': asmr_worker.worker.on_attacked,
			'detect_headpet': asmr_worker.worker.on_detect_headpet,
			'velocity_magnitude': asmr_worker.worker.set_velocity_magnitude,
		}
		osc_detectors = conf.osc_detectors or {}
		for key, cb in detection_map.items():
			detector_path = osc_detectors.get(key, None)
			if detector_path:
				disp.map(detector_path, wrap_into_async_osc_bool(cb))
			else:
				log.warning(f'No OSC avatar parameter path for "{key}" found in config, {key} will not work')

		# Some plugins may have been loaded earlier (before the dispatcher existed).
		# Re-run their on_load now that the dispatcher is available so they can
		# register OSC handlers (inhibitors, detectors, etc.). This is idempotent
		# for plugins that already registered handlers.
		for name, plugin in loaded_plugins.items():
			try:
				await plugin.on_load(
					conf=conf,
					vrc=vrc,
					main_loop=main_loop,
					task_group=task_group,
				)
			except Exception as e:
				log.exception(f'Failed to re-run on_load for plugin {name}: {e}')
		# disp.set_default_handler(print)

		server_details = await vrc_osc(NAME, disp, zeroconf=conf.zeroconf)
		log.info(
			f'Server started: http://{server_details.osc_host}:{server_details.http_port} osc_port={server_details.osc_port}'
		)
		log.info(
			f'Example: sendosc {server_details.osc_host} {server_details.osc_port} {osc_detectors.get("bullet", "/avatar/parameters/???")} b true'
		)

		vr = await get_vr_system(openvr.VRApplication_Overlay, task_group=task_group)

		asmr_worker_routine = spawn_task(
			asmr_worker.worker.start(vrc, vr, loaded_plugins=loaded_plugins, senders=conf.senders),
			loop=task_group,
			name='asmr_worker',
		)

		try:
			while True:
				if sys.stdout:
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


async def main():
	global main_loop
	main_loop = asyncio.get_event_loop()

	had_debug = main_loop.get_debug()
	if had_debug:
		main_loop.set_debug(False)

	async with asyncio.TaskGroup() as tg:
		await load_plugins(task_group=tg)

		if conf.install_to_steamvr:
			await reg_openvr(tg)

		await openvr_actions.reg_openvr_actions(main_loop, task_group=tg)  # pyright: ignore[reportArgumentType]
		asmr_worker_handles = asmr_worker.register_actions()

		if had_debug or conf.debug:
			main_loop.set_debug(True)

		await init_main(tg)


if __name__ == '__main__':
	asyncio.run(main())
