#!/usr/bin/env python

# TODO: Allow steamvr/devices to come and go


import sys
import math
import time
import openvr
import openvr.error_code
from asyncio import sleep

# import pygame
import audio_visualization
import plugin_zbye

from utils import getDeviceIDbySerial, wait_controllers, dump_devices, TrackConfig

# audio_visualization.init()
""""
init_errored = False
for i in range(9999):
	try:
		vr_system = openvr.init(openvr.VRApplication_Background)
	except openvr.error_code.InitError_Init_NoServerForBackgroundApp:
		if not init_errored:
			init_errored = True
			print('Waiting for SteamVR...')
		time.sleep(13.20)
		continue
	break
"""
vr_system: openvr.IVRSystem | None = None

trackings: list[TrackConfig] = []

# https://github.com/cmbruns/pyopenvr/blob/f466e1001d0db1d6ff4efdab0529747cf8a6fdee/src/samples/objmesh/test_obj.py#L734

# getControllerState
# https://gist.github.com/awesomebytes/75daab3adb62b331f21ecf3a03b3ab46

SCALE = 1.0
prev_ts = False


async def loop():
	await sleep(0.1)
	if not vr_system:
		return

	global prev_ts
	poses = vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, trackings)
	now = time.time()

	ft = now - (prev_ts or now)
	prev_ts = now
	ft = ft > 0.9 and 0.9 or ft <= 0.0001 and 0.0001 or ft

	plugin_zbye.on_tick(now, ft, poses)
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
			if tap_detected and not t.tapped:
				t.tapped = True
				t.send_untap = True
				t.set_tap_telemetry(1)
				print('TAP', name)
			elif t.tapped and not tap_detected:
				t.tapped = False

			if name == 'left':
				audio_visualization.set_volume_l(speed)
			elif name == 'right':
				# print("accel %3.2f vel=%3.2f" % ((velocity_up-ov)/(now-ot),velocity_up))
				audio_visualization.set_volume_r(speed)
		# print(speed)
		# sys.stdout.flush()
	for t in trackings:
		if t.send_untap:
			t.send_untap = False
			# print("UNTAP",t.name)
			t.set_tap_telemetry(0.0)


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
		if await loop() == True:
			break


async def start(client, _vr_system: openvr.IVRSystem):
	global oscClient, trackings, vr_system
	vr_system = _vr_system
	oscClient = client

	trackings.append(
		TrackConfig(
			name='left',
			osc_message='/avatar/parameters/petting_volume',
			osc_tap_message='/avatar/parameters/sound_taps_left',
			oscClient=oscClient,
			serial=None,
		)
	)
	trackings.append(
		TrackConfig(
			name='right',
			osc_message='/avatar/parameters/petting_volume_r',
			osc_tap_message='/avatar/parameters/sound_taps_right',
			oscClient=oscClient,
			serial=None,
		)
	)

	controllers = await wait_controllers(vr_system)
	if not controllers:
		return
	plugin_zbye.init(vr_system, controllers)

	dump_devices(vr_system)
	await run(controllers)
