import logging
import asyncio
import os
import sys
import json

# vrchat_oscquery provides zeroconf
import coloredlogs
from pythonosc.dispatcher import Dispatcher
import asmr_worker
from vrchat_oscquery.common import vrc_client
import vrchat_oscquery.common
import pluginhelper
import openvr
import openvr.error_code
import config_reader
from utils import (
	fatal,
	exit as _exit,
	spawn_task,
	FROZEN,
	EXEDIR,
	DEBUGGER,
	show_console,
	vrc_osc,
	get_vr_system,
	set_console_title,
)
from tendo import singleton
import importlib
import pkgutil

NAME = 'vr_asmr_petting'

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
try:
	me = singleton.SingleInstance(lockfile=f'{NAME}.lock')
except singleton.SingleInstanceException:
	fatal(
		'Another instance of this program is already running!',
		detail=f'Another instance of this program is already running. If you are sure that this is not the case, delete the lock file {NAME}.lock in the current directory and try again.',
		nodecor=True,
	)
	os._exit(1)

conf.run_count = (conf.run_count or 0) + 1
asmr_worker.worker.tapping_enabled = bool(conf.autotapping_enabled)
asmr_worker.worker.autopet_on_detect = bool(conf.autopet_on_detect)
asmr_worker.worker.autopet_osc_path = conf.autopet_osc_path
config_reader.save_config(conf)

if conf.debug and os.name == 'nt' and not HAS_TTY:
	show_console()
	logging.basicConfig(level=logging.DEBUG, force=True)

set_console_title('VR ASMR Petting')

if conf.debug_audio_visualization:
	asmr_worker.audio_visualization.init()

if conf.vrc_osc_ip:
	vrchat_oscquery.common.APP_HOST = conf.vrc_osc_ip
	vrchat_oscquery.common.VRC_HOST = conf.vrc_osc_ip
if conf.vrc_osc_port:
	vrchat_oscquery.common.VRC_PORT = conf.vrc_osc_port


def exit(n=0):
	_exit(n)


log.info(f'EXEDIR: {EXEDIR}')
log.info(f'FROZEN: {FROZEN}')
log.info(f'DEBUGGER: {DEBUGGER}')


main_loop = asyncio.new_event_loop()  # type: ignore

vrc = vrc_client()
asmr_worker_routine = None
AVATAR_CHANGE_PARAMETER = '/avatar/change'
loaded_plugins: dict[str, pluginhelper.VRPlugin] = {}


async def reg_openvr():
	log.info('Registering OpenVR autostart...')
	global _vr_system
	try:
		_vr_system = await get_vr_system(openvr.VRApplication_Overlay, loop=main_loop)

		log.info(
			'Installing to SteamVR: %s %s',
			EXEDIR / 'app.vrmanifest',
			openvr.VRApplications().addApplicationManifest(str((EXEDIR / 'app.vrmanifest').resolve()), True),
		)
		print('I AM ', os.getpid(), 'aka', openvr.VRApplications().getApplicationKeyByProcessId(os.getpid()))
		print('ASMR IS', openvr.VRApplications().getApplicationProcessId('python1320.vr_asmr_petting'))
	except Exception as e:
		fatal(str(e))


async def reg_openvr_actions():
	log.info('Registering OpenVR actions...')
	try:
		_vr_system = await get_vr_system(openvr.VRApplication_Overlay, loop=main_loop)
		action_manifest_path = str((EXEDIR / 'actions.json').resolve())
		log.info('Registering action manifest: %s', action_manifest_path)

		error = openvr.VRInput().setActionManifestPath(action_manifest_path)
		if error is not None and error != 0:
			log.error(f'Error setting action manifest path: {action_manifest_path}, OpenVR Error: {error}')

		with open(action_manifest_path, 'r') as f:
			actions_json = json.load(f)
		print(f'Actions from actions.json: {actions_json.get("actions", [])}')

		action_handle_left = openvr.VRInput().getActionHandle('/actions/default/in/TouchLeft')
		if action_handle_left is None:
			log.error('Error getting action handle: /actions/default/in/TouchLeft')
		action_handle_right = openvr.VRInput().getActionHandle('/actions/default/in/TouchRight')
		if action_handle_right is None:
			log.error('Error getting action handle: /actions/default/in/TouchRight')
		action_set_handle = openvr.VRInput().getActionSetHandle('/actions/default')
		if action_set_handle is None:
			log.error('Error getting action set handle: /actions/default')

		log.info(f'Action handles: left={action_handle_left}, right={action_handle_right}, set={action_set_handle}')

		if action_handle_left is None or action_handle_right is None or action_set_handle is None:
			log.error('Failed to get action handles, not starting polling')
		else:
			spawn_task(
				poll_openvr_actions(_vr_system, action_handle_left, action_handle_right), name='poll_openvr_actions'
			)

	except Exception as e:
		fatal(str(e))


async def poll_openvr_actions(_vr_system, action_handle_left, action_handle_right):
	prev_states = {action_handle_left: None, action_handle_right: None}

	action_set = openvr.VRInput().getActionSetHandle('/actions/default')
	try:
		pass  # openvr.VRInput().openBindingUI('', action_set, 0, True)
	except Exception as e:
		log.error(f'Error opening binding UI: {e}')
	while True:
		active_action_sets = (openvr.VRActiveActionSet_t * 1)()
		active_action_set = active_action_sets[0]
		active_action_set.ulActionSet = action_set
		openvr.VRInput().updateActionState(active_action_sets)

		actions = [
			(action_handle_left, 'TouchLeft'),
			(action_handle_right, 'TouchRight'),
		]
		for handle, name in actions:
			try:
				state = openvr.VRInput().getDigitalActionData(handle, openvr.k_ulInvalidInputValueHandle)
			except openvr.error_code.InputError_InvalidHandle as e:
				continue
			if prev_states.get(handle) is not None and prev_states[handle] != state.bState:
				print(f'{name}: bState={state.bState}, bActive={state.bActive}')
			prev_states[handle] = state.bState
		await asyncio.sleep(0.1)


async def load_plugins():
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
					if not await plugin.on_load(conf=conf, vrc=vrc, main_loop=main_loop):
						continue
				except Exception as e:
					log.exception(f'Failed to load plugin {name}: {e}')
					fatal(f'Failed to load plugin {name}: {e}')
					raise

				loaded_plugins[name] = plugin  # type: ignore # TODO: REFACTOR: use classes!!

	log.info('Loaded plugins:')
	for name, plugin in loaded_plugins.items():
		log.info(f' - {name}')


async def init_main():
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
		disp = Dispatcher()
		pluginhelper.set_osc_dispatcher(disp)

		disp.map(AVATAR_CHANGE_PARAMETER, avatar_change)

		def wrap_into_async_osc_bool(cb):
			def _wrapper(key, *val):
				# log.debug(f'{key} {val}')
				# TODO: queue?
				spawn_task(cb(bool(val[0])))

			return _wrapper

		detection_map = {
			'enabled': asmr_worker.worker.on_enabled,
			'tapping_enabled': asmr_worker.worker.set_tapping_enabled,
			'attacked': asmr_worker.worker.on_attacked,
			'detect_headpet': asmr_worker.worker.on_detect_headpet,
		}
		osc_detectors = conf.osc_detectors or {}
		for key, cb in detection_map.items():
			detector_path = osc_detectors.get(key, None)
			if detector_path:
				disp.map(detector_path, wrap_into_async_osc_bool(cb))
			else:
				log.warning(f'No OSC avatar parameter path for "{key}" found in config, {key} will not work')
		# disp.set_default_handler(print)

		server_details = await vrc_osc(NAME, disp, zeroconf=conf.zeroconf)
		log.info(
			f'Server started: http://{server_details.osc_host}:{server_details.http_port} osc_port={server_details.osc_port}'
		)
		log.info(
			f'Example: sendosc {server_details.osc_host} {server_details.osc_port} {osc_detectors.get("bullet", "/avatar/parameters/???")} b true'
		)
		vr = await get_vr_system(openvr.VRApplication_Overlay)

		asmr_worker_routine = spawn_task(
			asmr_worker.worker.start(vrc, vr, loaded_plugins=loaded_plugins, senders=conf.senders), name='asmr_worker'
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


if __name__ == '__main__':
	had_debug = main_loop.get_debug()
	if had_debug:
		main_loop.set_debug(False)
	main_loop.run_until_complete(load_plugins())

	if conf.install_to_steamvr:
		main_loop.run_until_complete(reg_openvr())

	if had_debug or conf.debug:
		main_loop.set_debug(True)

	main_loop.run_until_complete(reg_openvr_actions())
	main_loop.run_until_complete(init_main())
