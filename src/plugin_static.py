"""
move hands fast, catch on fire
"""

import openvr
import math
import time
from functools import wraps
import openvr
import numpy

from utils import *


class State:
	pos = 0


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


def init(vr_system, controllers):
	pass  # TODO


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
	pass


async def on_load(conf=None, vrc=None, main_loop=None):
	return False


async def on_vr(vr=None, controllers=None):
	pass


async def on_start():
	pass
