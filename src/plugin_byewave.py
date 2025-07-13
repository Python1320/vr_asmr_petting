import openvr
import math
import numpy

import pluginhelper

NAME = 'byewave'


class State:
	pos = 0
	controllers: list[int] = []


state = State()


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


def on_tick(now, ft, poses):
	(pose_lh, vel_lh) = getpose(poses, state.controllers[1])  # type: ignore
	(pose_rh, vel_rh) = getpose(poses, state.controllers[0])  # type: ignore
	(pose_hmd, vel_hmd) = getpose(poses, openvr.k_unTrackedDeviceIndex_Hmd)
	if not pose_lh or not pose_rh or not pose_hmd:
		return
	# print("z",-pose_rh[2])
	# print("___ y",-pose_rh[0])
	# print("___ x",-pose_rh[1])
	# print("___ WTF ",-pose_rh[3])

	d_hr = math.dist(pose_rh, pose_hmd)
	d_hl = math.dist(pose_lh, pose_hmd)
	d_r = d_hl - d_hr

	if vel_lh > 0.1 or vel_rh > 0.1 or vel_hmd > 0.1:
		return

	if (
		pose_hmd[2] > pose_rh[2] or pose_hmd[2] < pose_lh[2] or d_r < 0.3
	):  # or math.dist(pose_rh,pose_hmd)>math.dist(pose_lh,pose_hmd):
		godown(ft, False)
	else:
		godown(ft, True)


def godown(ft, go_down):
	# TODO: handle movement quantas with ft
	if go_down and state.pos < 30:
		state.pos += 1
		move_z(ft, True)
	elif not go_down and state.pos > 0:
		state.pos -= 1
		move_z(ft, False)


def move_z(ft, golower=False):
	openvr.VRChaperoneSetup().revertWorkingCopy()
	standing_zero_to_raw_tracking_pose = openvr.VRChaperoneSetup().getWorkingStandingZeroPoseToRawTrackingPose()
	pose = standing_zero_to_raw_tracking_pose[1]
	MOVESZ = 0.1
	pose[1][3] += golower and (MOVESZ) or -MOVESZ
	openvr.VRChaperoneSetup().setWorkingStandingZeroPoseToRawTrackingPose(pose)
	openvr.VRChaperoneSetup().commitWorkingCopy(openvr.EChaperoneConfigFile_Live)


async def on_load(conf: pluginhelper.TYPE_CONF, vrc: pluginhelper.TYPE_VRC, main_loop: pluginhelper.TYPE_MAIN_LOOP):
	plugin_conf = conf.plugins.get(NAME)

	if not plugin_conf:
		return False

	if not plugin_conf.enabled:
		return False

	pluginhelper.register_plugin_tick_callback(NAME, on_tick)
	return True


async def on_vr(vr=None, controllers=None):
	state.controllers = controllers  # type: ignore


async def on_start():
	return  # we run on tick


if __name__ == '__main__':
	"""	
	vr_system = openvr.init(openvr.VRApplication_Background)
	for _ in range(5):
		for i in range(50):
			time.sleep(0.01)
			on_tick(False,0.1)
		for i in range(50):
			time.sleep(0.01)
			on_tick(True,0.1)
"""
