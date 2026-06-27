#!/usr/bin/env python

# TODO: Allow steamvr/devices to come and go


import math
import time
import openvr
import openvr.error_code
from asyncio import sleep
import logging

import config_reader
from pluginhelper import VRPlugin, plugin_tick_callbacks

import audio_visualization


from utils import getDeviceIDbySerial, wait_controllers, dump_devices, TrackConfig
from vrappcommon.vrutils import VRChatUDP


class ASMRWorker:
	oscClient: VRChatUDP
	vr_system: openvr.IVRSystem

	enabled: bool = False
	enabled_alt: bool = False
	tapping_enabled: bool = True

	autopet_on_detect: bool = False
	autopet_osc_path: str | None = None
	is_petting: bool = False
	detect_headpet: bool = False
	velocity_magnitude_suppress_tap: bool = False

	attacked: bool = False
	attack_front: bool = False
	attack_back: bool = False
	SCALE = 1.0
	prev_ts: float | bool = False
	poses: openvr.Array[openvr.TrackedDevicePose_t] | None
	petting_sound_enable_move_threshold: float = 0.0
	petting_sound_touch_fade_seconds: float = 0.5
	arm_on_touch: bool = False
	arm_touch_state: dict[str, bool]
	arm_touch_ready: dict[str, bool]

	def __init__(self) -> None:

		self.poses = None
		self.trackings: list[TrackConfig] = []
		self.arm_touch_state = {'left': False, 'right': False}
		self.arm_touch_ready = {'left': False, 'right': False}
		self.sticky_state = {'left': False, 'right': False}
		self._sticky_touch_released = {'left': False, 'right': False}

	async def on_enabled(self, e: bool) -> None:
		self.enabled = e
		logging.debug(f'ASMR = {self.enabled}')
		if not self.enabled and not self.enabled_alt:
			self.is_petting = False
		# If enabling, suppress per-track sound until movement drops near zero
		if e:
			threshold = self.petting_sound_enable_move_threshold or 0.0
			for t in self.trackings:
				if getattr(t, 'last_raw_speed', 0.0) > threshold:
					t.suppress_until_zero = True

	async def on_enabled_alt(self, e: bool) -> None:
		self.enabled_alt = e
		logging.debug(f'ASMR (alt) = {self.enabled_alt}')
		if not self.enabled and not self.enabled_alt:
			self.is_petting = False
		# If enabling alt, suppress per-track sound until movement drops near zero
		if e:
			threshold = self.petting_sound_enable_move_threshold or 0.0
			for t in self.trackings:
				if getattr(t, 'last_raw_speed', 0.0) > threshold:
					t.suppress_until_zero = True

	async def on_detect_headpet(self, e: bool) -> None:
		if self.detect_headpet == e:
			return
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

	async def set_velocity_magnitude(self, magnitude_nonzero: bool) -> None:
		if magnitude_nonzero != self.velocity_magnitude_suppress_tap:
			self.velocity_magnitude_suppress_tap = magnitude_nonzero
			logging.debug(f'Velocity magnitude suppress tap = {self.velocity_magnitude_suppress_tap}')

	async def set_arm_touch_state(self, hand: str, touched: bool) -> None:
		if hand not in ('left', 'right'):
			return
		current = self.arm_touch_state.get(hand, False)
		if current == touched:
			return
		self.arm_touch_state[hand] = touched
		# find matching track and set up fade timer on release/acquire
		for t in self.trackings:
			if t.name == hand:
				fade = float(self.petting_sound_touch_fade_seconds or 0.5)
				if not touched:
					self.arm_touch_ready[hand] = False
					# record the telemetry start value so fade cannot increase above it
					t.touch_fade_start_value = getattr(t, 'last_sent_speed', 0.0)
					t.touch_fade_until = time.time() + fade
					t.touch_fade_in_until = 0.0
				else:
					# start fade-in on acquire
					self.arm_touch_ready[hand] = False
					t.touch_fade_in_start_value = getattr(t, 'last_sent_speed', 0.0)
					t.touch_fade_in_until = time.time() + fade
					t.touch_fade_until = 0.0
		logging.debug(f'Arm touch {hand} = {touched}')

	async def toggle_sticky(self, hand: str) -> None:
		if hand not in ('left', 'right'):
			return
		if self.sticky_state[hand]:
			self.sticky_state[hand] = False
			self._sticky_touch_released[hand] = False
			import openvr_actions
			physically_touched = openvr_actions.state.get(
				f'/actions/default/in/Touch{hand.capitalize()}', False
			)
			logging.debug(f'Sticky {hand} OFF (physical touch = {physically_touched})')
			await self.set_arm_touch_state(hand, physically_touched)
		else:
			self.sticky_state[hand] = True
			self._sticky_touch_released[hand] = False
			logging.debug(f'Sticky {hand} ON')
			await self.set_arm_touch_state(hand, True)

	async def cancel_sticky(self, hand: str) -> None:
		if hand not in ('left', 'right'):
			return
		if not self.sticky_state[hand]:
			return
		self.sticky_state[hand] = False
		self._sticky_touch_released[hand] = False
		import openvr_actions
		physically_touched = openvr_actions.state.get(
			f'/actions/default/in/Touch{hand.capitalize()}', False
		)
		logging.debug(f'Sticky {hand} CANCELLED (physical touch = {physically_touched})')
		await self.set_arm_touch_state(hand, physically_touched)

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

		self.poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
			openvr.TrackingUniverseStanding, 0, self.poses or []
		)

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
			# If device disconnected or pose invalid, report only on transition from OK -> not-OK
			if not pose.bDeviceIsConnected:
				if t.was_okay:
					logging.warning(f'Not connected {name}')
					t.was_okay = False
				t.set_telemetry(0.0)
				continue
			if not pose.bPoseIsValid:
				if t.was_okay:
					logging.warning(f'Not valid {name}')
					t.was_okay = False
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
			raw_speed = min(max(velocity * self.SCALE, 0), 1)
			speed = raw_speed
			# Arm-on-touch: allow fadeout on release and fadein on acquire
			if self.arm_on_touch and name in ('left', 'right'):
				touched = self.arm_touch_state.get(name, False)
				fade_seconds = float(self.petting_sound_touch_fade_seconds or 0.5)
				if not touched:
					# if we have an active fade timer, apply fade factor
					fade_until = getattr(t, 'touch_fade_until', 0.0) or 0.0
					if fade_until > now:
						remaining = fade_until - now
						factor = max(remaining / fade_seconds, 0.0)
						candidate = raw_speed * factor
						start_val = getattr(t, 'touch_fade_start_value', 0.0) or 0.0
						# Never allow fade to increase above the start value recorded at release
						speed = min(start_val, candidate)
					else:
						speed = 0.0
				else:
					# fade in on acquire
					fade_in_until = getattr(t, 'touch_fade_in_until', 0.0) or 0.0
					if fade_in_until > now:
						remaining = fade_in_until - now
						factor = max((fade_seconds - remaining) / fade_seconds, 0.0)
						start_val = getattr(t, 'touch_fade_in_start_value', 0.0) or 0.0
						speed = start_val + (raw_speed - start_val) * factor
						if speed > raw_speed:
							speed = raw_speed
					else:
						speed = raw_speed
					if getattr(t, 'suppress_until_zero', False):
						threshold = self.petting_sound_enable_move_threshold or 0.0
						if raw_speed <= threshold:
							t.suppress_until_zero = False
						else:
							speed = 0.0
			# Global enable clamp
			if not self.enabled and not self.enabled_alt:
				speed = 0.0
			t.set_telemetry(speed)
			# record last sent telemetry so fades can reference the start value
			try:
				t.last_sent_speed = float(speed)
			except Exception:
				t.last_sent_speed = 0.0
			t.last_raw_speed = raw_speed
			# mark device as seen in a good state (connected + valid)
			if not t.was_okay:
				logging.info(f'Device recovered: {name}')
				t.was_okay = True
			if name == 'left' or name == 'right':
				# TODO: Both direction major acceleration required: unlock_tap/last_accelerated
				# TODO: Detect joystick being pressed and disable tap (maybe via OSC?)
				if (
					tap_detected
					and not t.tapped
					and self.tapping_enabled
					and not self.enabled
					and not self.enabled_alt
					and not self.velocity_magnitude_suppress_tap
				):
					t.tapped = True
					t.send_untap = now + 0.101
					t.set_tap_telemetry(1)
					logging.info(f'TAP! {name}')
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


def register_actions():
	import openvr_actions

	def make_touch_handler(hand: str):
		prev_physical = [False]
		async def handler(handle):
			physically_touched = bool(openvr_actions.state.get(handle.path, False))
			if worker.sticky_state.get(hand, False):
				if prev_physical[0] and not physically_touched:
					worker._sticky_touch_released[hand] = True
				prev_physical[0] = physically_touched
				if not physically_touched:
					return
				elif worker._sticky_touch_released.get(hand, False):
					worker.sticky_state[hand] = False
					worker._sticky_touch_released[hand] = False
					logging.debug(f'Sticky {hand} cleared by physical touch')
					await worker.set_arm_touch_state(hand, True)
				return
			prev_physical[0] = physically_touched
			await worker.set_arm_touch_state(hand, physically_touched)
		return handler

	left = openvr_actions.get_handle('/actions/default/in/TouchLeft')
	right = openvr_actions.get_handle('/actions/default/in/TouchRight')
	sticky_left = openvr_actions.get_handle('/actions/default/in/StickyTouchLeft')
	sticky_right = openvr_actions.get_handle('/actions/default/in/StickyTouchRight')

	openvr_actions.listen(left, make_touch_handler('left'))
	openvr_actions.listen(right, make_touch_handler('right'))

	def make_sticky_handler(hand: str):
		prev = [False]
		async def handler(handle):
			pressed = bool(openvr_actions.state.get(handle.path, False))
			rising = pressed and not prev[0]
			prev[0] = pressed
			if rising and not worker.sticky_state.get(hand, False):
				await worker.toggle_sticky(hand)
		return handler

	openvr_actions.listen(sticky_left, make_sticky_handler('left'))
	openvr_actions.listen(sticky_right, make_sticky_handler('right'))

	sticky_cancel_left = openvr_actions.get_handle('/actions/default/in/StickyCancelLeft')
	sticky_cancel_right = openvr_actions.get_handle('/actions/default/in/StickyCancelRight')

	def make_sticky_cancel_handler(hand: str):
		prev = [False]
		async def handler(handle):
			pressed = bool(openvr_actions.state.get(handle.path, False))
			rising = pressed and not prev[0]
			prev[0] = pressed
			if rising:
				sticky_on_path = f'/actions/default/in/StickyTouch{hand.capitalize()}'
				on_held = bool(openvr_actions.state.get(sticky_on_path, False))
				if not on_held:
					await worker.cancel_sticky(hand)
		return handler

	openvr_actions.listen(sticky_cancel_left, make_sticky_cancel_handler('left'))
	openvr_actions.listen(sticky_cancel_right, make_sticky_cancel_handler('right'))

	return left, right
