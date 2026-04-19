#!/usr/bin/env python

# TODO: Allow steamvr/devices to come and go


import math
import time
import openvr
import openvr.error_code
from asyncio import sleep
import logging
from typing import Any

import config_reader
from pluginhelper import VRPlugin, plugin_tick_callbacks

import audio_visualization


from utils import getDeviceIDbySerial, wait_controllers, dump_devices, TrackConfig


class ASMRWorker:
	def __init__(self) -> None:
		self.vr_system: openvr.IVRSystem | None = None
		self.trackings: list[TrackConfig] = []
		self.SCALE = 1.0
		self.prev_ts: float | bool = False
		self.poses: list[openvr.TrackedDevicePose_t] = []

		self.enabled: bool = False
		self.enabled_alt: bool = False
		self.tapping_enabled: bool = True

		self.autopet_on_detect: bool = False
		self.autopet_osc_path: str | None = None
		self.is_petting: bool = False
		self.detect_headpet: bool = False

		self.attacked: bool = False
		self.attack_front: bool = False
		self.attack_back: bool = False

		self.oscClient: Any | None = None

	async def on_enabled(self, e: bool) -> None:
		self.enabled = e
		logging.debug(f'ASMR = {self.enabled}')
		if not self.enabled and not self.enabled_alt:
			self.is_petting = False

	async def on_enabled_alt(self, e: bool) -> None:
		self.enabled_alt = e
		logging.debug(f'ASMR (alt) = {self.enabled_alt}')
		if not self.enabled and not self.enabled_alt:
			self.is_petting = False

	async def on_detect_headpet(self, e: bool) -> None:
		self.detect_headpet = e
		logging.debug(f'Detect headpet = {self.detect_headpet}')
		if (
			self.autopet_on_detect
			and self.detect_headpet
			and self.autopet_osc_path
			and not self.enabled
			and not self.enabled_alt
			and not self.is_petting
		):
			self.is_petting = True
			logging.info(f'Auto-petting triggered by detect_headpet, sending {self.autopet_osc_path} 1')
			self.oscClient.send_message(self.autopet_osc_path, [1])

	async def set_tapping_enabled(self, enabled: bool) -> None:
		self.tapping_enabled = enabled
		logging.debug(f'Tap = {self.tapping_enabled}')

	async def on_attacked(self, e: bool) -> None:
		self.attacked = e
		logging.debug(f'Attacked = {self.attacked}')

	async def on_attack_front(self, e: bool) -> None:
		self.attack_front = e
		logging.debug(f'Attack front = {self.attack_front}')

	async def on_attack_back(self, e: bool) -> None:
		self.attack_back = e
		logging.debug(f'Attack back = {self.attack_back}')

	async def loop(self) -> None:
		await sleep(0.101)
		if not self.vr_system:
			return

		self.poses = self.vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, self.poses)
		now = time.time()

		ft = now - (self.prev_ts or now)
		self.prev_ts = now
		ft = ft > 0.9 and 0.9 or ft <= 0.0001 and 0.0001 or ft

		for plugin in plugin_tick_callbacks.values():
			await plugin(now, ft, self.poses)

		for t in self.trackings:
			delta = t.delta
			name = t.name

			pose: openvr.TrackedDevicePose_t = self.poses[t.device_id]
			if not pose.bDeviceIsConnected:
				print('Not connected', name)
				t.set_telemetry(0.0)
				continue
			if not pose.bPoseIsValid:
				print('Not valid', name)
				t.set_telemetry(0.0)
				continue

			velocity = math.hypot(*pose.vVelocity)
			velocity_up = pose.vVelocity[1]
			ov = delta[0]
			ot = delta[1]
			delta[0] = velocity_up
			delta[1] = now
			accel = (velocity_up - ov) / (now - ot)
			tap_detected = accel > 15 and ov < 0
			# if name=="left" and abs(accel)>4:
			# r	print(accel)
			speed = min(max(velocity * self.SCALE, 0), 1)
			t.set_telemetry(speed)
			if name == 'left' or name == 'right':
				# TODO: Both direction major acceleration required: unlock_tap/last_accelerated
				if tap_detected and not t.tapped and self.tapping_enabled and not self.enabled and not self.enabled_alt:
					t.tapped = True
					t.send_untap = now + 0.101
					t.set_tap_telemetry(1)
					print('TAP!', name)
				elif t.tapped and not tap_detected:
					t.tapped = False

				if name == 'left':
					audio_visualization.set_volume_l(speed)
				elif name == 'right':
					# print("accel %3.2f vel=%3.2f" % ((velocity_up-ov)/(now-ot),velocity_up))
					audio_visualization.set_volume_r(speed)

		for t in self.trackings:
			if t.send_untap and now > t.send_untap:
				t.send_untap = False
				# print("UNTAP",t.name)
				t.set_tap_telemetry(0)

	async def run(self, controllers):
		for t in self.trackings:
			if t.name == 'left':
				t.device_id = controllers[0]
			elif t.name == 'right':
				t.device_id = controllers[1]
			elif t.name == 'head':
				t.device_id = controllers[2]
			else:
				t.name = t.name or t.serial or '???'
				device_id = getDeviceIDbySerial(t.serial or t.name, self.vr_system)
				if device_id:
					t.device_id = device_id

		for conf in self.trackings:
			print('Tracking: ', conf.__dict__)
		for i in range(999999999):
			if await self.loop():
				break

	async def start(
		self,
		client,
		_vr_system: openvr.IVRSystem,
		loaded_plugins: dict[str, VRPlugin],
		senders: config_reader.Senders,
	) -> None:
		self.vr_system = _vr_system
		self.oscClient = client
		self.trackings.clear()

		self.trackings.append(
			TrackConfig(
				name='left',
				osc_message=senders.volume_left or '/avatar/parameters/petting_volume',
				osc_tap_message=senders.sound_taps_left or '/avatar/parameters/sound_taps_left',
				oscClient=self.oscClient,
				serial=None,
			)
		)
		self.trackings.append(
			TrackConfig(
				name='right',
				osc_message=senders.volume_right or '/avatar/parameters/petting_volume_r',
				osc_tap_message=senders.sound_taps_right or '/avatar/parameters/sound_taps_right',
				oscClient=self.oscClient,
				serial=None,
			)
		)

		controllers = await wait_controllers(self.vr_system)
		if not controllers:
			return

		for plugin in loaded_plugins.values():
			await plugin.on_vr(vr=self.vr_system, controllers=controllers)

		dump_devices(self.vr_system)

		logging.info('Starting plugins...')
		for plugin in loaded_plugins.values():
			await plugin.on_start()

		logging.info('Finished starting plugins, running main loop...')

		await self.run(controllers)

worker = ASMRWorker()
