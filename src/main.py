import logging
import asyncio
import json
import os
import sys
import time
import traceback
import ctypes
from typing import Any, List

# vrchat_oscquery provides zeroconf
import coloredlogs
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import SimpleUDPClient
from vrchat_oscquery.common import vrc_client

import openvr
from pathlib import Path
from datetime import datetime
import config_reader
from utils import fatal, exit as _exit, spawn_task, FROZEN, EXEDIR, DEBUGGER, show_console, vrc_osc

print('VR Audience Fire starting...')


NAME = 'vr_audience_fire'
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


class AudienceFire:
	def __init__(self):
		self.fire = False
		self.water = False
		self.water_last_changed = None
		self.fire_last_changed = None
		self._water_task = None

	async def on_fire(self, on=True):
		if not on:
			return
		log.debug(f'on_fire={on}')
		await self.set_fire(on)

	async def on_water(self, on=True):
		if not on:
			return
		log.debug(f'on_water={on}')
		await self.set_water(on)

	async def on_water_effect(self, on):
		log.debug(f'on_water_effect={on}')
		self.water = on

	async def on_fire_effect(self, on):
		log.debug(f'on_fire_effect={on}')
		self.fire = on

	async def set_fire(self, on=True):
		log.debug(f'set_fire={on}')
		if on and self.water:
			await self.set_water(False)
		self.fire = on
		self.fire_last_changed = datetime.now()
		await self.send_fire(on)

	async def set_water(self, on=True):
		log.debug(f'set_water={on}')
		if on and self.fire:
			await self.set_fire(False)
		self.water = on
		self.water_last_changed = datetime.now()
		await self.send_water(on)

		if on:
			if self._water_task:
				self._water_task.cancel()
			self._water_task = asyncio.create_task(self._auto_stop_water())

	async def _auto_stop_water(self):
		try:
			await asyncio.sleep(5)
			await self.set_water(False)
		except asyncio.CancelledError:
			pass

	async def send_water(self, on=True):
		senders = conf.senders
		log.info(f'send_water on={on} at {self.water_last_changed}')
		for msg, payload in ((senders.water if on else senders.water_off) or {}).items():
			log.debug(f'send_water {msg} {payload}')
			if vrc:
				vrc.send_message(msg, payload)

	async def send_fire(self, on=True):
		log.info(f'send_fire on={on}')
		senders = conf.senders
		for msg, payload in ((senders.fire if on else senders.fire_off) or {}).items():
			log.debug(f'send_fire {msg} {payload}')
			if vrc:
				vrc.send_message(msg, payload)

	async def on_reset(self):
		log.info('reset')
		if self._water_task:
			self._water_task.cancel()

	async def on_bullet(self, on=True):
		log.info(f'on_bullet {on}')
		if on:
			await self.set_fire(True)


def exit(n=0):
	_exit(n)


log.info(f'EXEDIR: {EXEDIR}')
log.info(f'FROZEN: {FROZEN}')
log.info(f'DEBUGGER: {DEBUGGER}')


main_loop = asyncio.new_event_loop()  # type: ignore
main_loop.set_debug(True)
vrc = vrc_client()


AVATAR_CHANGE_PARAMETER = '/avatar/change'


def reg_openvr():
	global application
	try:
		application = openvr.init(openvr.VRApplication_Utility)
		log.info(
			'Installing to SteamVR: %s %s',
			EXEDIR / 'app.vrmanifest',
			openvr.VRApplications().addApplicationManifest(str((EXEDIR / 'app.vrmanifest').resolve())),
		)

	except Exception as e:
		fatal(str(e))


async def init_main():
	global disp, vrc, osc_receiver, osc_server, qclient, audience_fire, transport, protocol, main_loop

	audience_fire = AudienceFire()

	def avatar_change(addr, value):
		log.info(f'Avatar changed/reset {addr} {value}...')
		spawn_task(audience_fire.on_reset())

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
			'water': audience_fire.on_water,
			'fire': audience_fire.on_fire,
			'water_effect': audience_fire.on_water_effect,
			'fire_effect': audience_fire.on_fire_effect,
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
			f'Example: sendosc {server_details.osc_host} {server_details.osc_port} {osc_detectors.get("fire", "/avatar/parameters/???")} b true'
		)
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
		reg_openvr()
	main_loop.run_until_complete(init_main())
