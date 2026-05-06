import openvr
import math
import numpy

import pluginhelper
from pythonosc.udp_client import SimpleUDPClient

NAME = 'static'


class State:
	pos = 0
	controllers: list[int] = []
	cumulative_movement: float = 0.0
	is_firing: bool = False
	last_fire_time: float = 0.0


state = State()

oscClient: SimpleUDPClient | None = None


# https://github.com/ValveSoftware/openvr/wiki/Matrix-Usage-Example
def convert_steam_vr_matrix(pose):
	return numpy.array(
		(
			(pose[0][0], pose[1][0], pose[2][0], 0.0),
			(pose[0][1], pose[1][1], pose[2][1], 0.0),
			(pose[0][2], pose[1][2], pose[2][2], 0.0),
			(pose[0][3], pose[1][3], pose[2][3], 1.0),
		),
		dtype=numpy.float32,
	)


def getpose(poses, device_id):
	pose: openvr.TrackedDevicePose_t = poses[device_id]
	if not pose.bDeviceIsConnected:
		return (False, False)
	if not pose.bPoseIsValid:
		return (False, False)
	mat = pose.mDeviceToAbsoluteTracking
	z = mat[1][3]
	x = mat[0][3]
	y = mat[2][3]
	xyz = (x, y, z)
	return (xyz, math.hypot(*pose.vVelocity))


async def on_tick(now, ft, poses):
	if not poses:
		return
	(pose_lh, vel_lh) = getpose(poses, state.controllers[1])  # type: ignore
	(pose_rh, vel_rh) = getpose(poses, state.controllers[0])  # type: ignore
	(pose_hmd, vel_hmd) = getpose(poses, openvr.k_unTrackedDeviceIndex_Hmd)
	if not pose_lh or not pose_rh or not pose_hmd:
		return

	d_hr = math.dist(pose_rh, pose_hmd)
	d_hl = math.dist(pose_lh, pose_hmd)
	d_r = d_hl - d_hr

	if vel_lh > 0.1 or vel_rh > 0.1 or vel_hmd > 0.1:
		state.cumulative_movement += 1
	elif state.cumulative_movement > 0:
		state.cumulative_movement -= 0.5

	moving_rapidly = vel_lh > 1.0 or vel_rh > 1.0

	if moving_rapidly and state.cumulative_movement > 20 and (now - state.last_fire_time) > 240:
		if not state.is_firing:
			state.is_firing = True
			state.last_fire_time = now
			state.cumulative_movement = 0.0
			print('FIRE: ON', vel_lh, vel_rh, state.cumulative_movement)
			if oscClient:
				oscClient.send_message('/avatar/parameters/fire', True)


async def on_load(conf: pluginhelper.TYPE_CONF, vrc: pluginhelper.TYPE_VRC, main_loop: pluginhelper.TYPE_MAIN_LOOP):
	global oscClient
	plugin_conf = conf.plugins.get(NAME)

	if not plugin_conf:
		return False

	if not plugin_conf.enabled:
		return False

	oscClient = vrc
	pluginhelper.register_plugin_tick_callback(NAME, on_tick)
	return True


async def on_vr(vr=None, controllers=None):
	state.controllers = controllers  # type: ignore


async def on_start():
	return  # we run on tick
