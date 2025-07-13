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


vr_system: openvr.IVRSystem | None = None

trackings: list[TrackConfig] = []

# https://github.com/cmbruns/pyopenvr/blob/f466e1001d0db1d6ff4efdab0529747cf8a6fdee/src/samples/objmesh/test_obj.py#L734

# getControllerState
# https://gist.github.com/awesomebytes/75daab3adb62b331f21ecf3a03b3ab46

SCALE = 1.0
prev_ts = False
poses = []

enabled = True
enabled_alt = True
tapping_enabled = True


# TODO: unused
def on_enabled(e: bool) -> None:
	global enabled
	enabled = e
	logging.debug(f'ASMR = {enabled}')


def on_enabled_alt(e: bool) -> None:
	global enabled_alt
	enabled_alt = e
	logging.debug(f'ASMR (alt) = {enabled_alt}')


def set_tapping_enabled(enabled: bool) -> None:
	global tapping_enabled
	tapping_enabled = enabled
	logging.debug(f'Tap = {tapping_enabled}')


async def loop() -> None:
	global poses
	await sleep(0.101)
	if not vr_system:
		return

	global prev_ts
	poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, poses)
	now = time.time()

	ft = now - (prev_ts or now)
	prev_ts = now
	ft = ft > 0.9 and 0.9 or ft <= 0.0001 and 0.0001 or ft

	for plugin in plugin_tick_callbacks.values():
		await plugin(now, ft, poses)

	for t in trackings:
		delta = t.delta
		name = t.name

		pose: openvr.TrackedDevicePose_t = poses[t.device_id]
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
		speed = min(max(velocity * SCALE, 0), 1)
		t.set_telemetry(speed)
		if name == 'left' or name == 'right':
			# TODO: Both direction major acceleration required: unlock_tap/last_accelerated
			if tap_detected and not t.tapped and tapping_enabled:
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

	for t in trackings:
		if t.send_untap and now > t.send_untap:
			t.send_untap = False
			# print("UNTAP",t.name)
			t.set_tap_telemetry(0)


async def run(controllers):
	for t in trackings:
		if t.name == 'left':
			t.device_id = controllers[0]
		elif t.name == 'right':
			t.device_id = controllers[1]
		elif t.name == 'head':
			t.device_id = controllers[2]
		else:
			t.name = t.name or t.serial or '???'
			device_id = getDeviceIDbySerial(t.serial or t.name, vr_system)
			if device_id:
				t.device_id = device_id

	for conf in trackings:
		print('Tracking: ', conf.__dict__)
	for i in range(999999999):
		if await loop():
			break


async def start(
	client, _vr_system: openvr.IVRSystem, loaded_plugins: dict[str, VRPlugin], senders: config_reader.Senders
) -> None:
	global oscClient, trackings, vr_system
	vr_system = _vr_system
	oscClient = client

	trackings.append(
		TrackConfig(
			name='left',
			osc_message=senders.volume_left or '/avatar/parameters/petting_volume',
			osc_tap_message=senders.sound_taps_left or '/avatar/parameters/sound_taps_left',
			oscClient=oscClient,
			serial=None,
		)
	)
	trackings.append(
		TrackConfig(
			name='right',
			osc_message=senders.volume_right or '/avatar/parameters/petting_volume_r',
			osc_tap_message=senders.sound_taps_right or '/avatar/parameters/sound_taps_right',
			oscClient=oscClient,
			serial=None,
		)
	)

	controllers = await wait_controllers(vr_system)
	if not controllers:
		return

	for plugin in loaded_plugins.values():
		await plugin.on_vr(vr=vr_system, controllers=controllers)

	dump_devices(vr_system)

	logging.info('Starting plugins...')
	for plugin in loaded_plugins.values():
		await plugin.on_start()

	logging.info('Finished starting plugins, running main loop...')

	await run(controllers)
