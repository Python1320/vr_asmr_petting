import openvr

import pluginhelper
import asmr_worker

NAME = 'bullet'


class State:
	pos = 0
	end_time = 0


state = State()


async def on_tick(now, ft, poses):
	if asmr_worker.worker.attacked and now < state.end_time:
		godown(ft, True)  # sink
	elif asmr_worker.worker.attacked and now >= state.end_time:
		state.end_time = now + 5
		print('BULLET: Attacked! Sinking for 5 seconds')
	elif state.end_time > 0 and now < state.end_time:
		godown(ft, False)  # rise back up
	elif state.end_time > 0 and now >= state.end_time:
		state.end_time = 0


def godown(ft, go_down):
	# TODO: handle movement quantas with ft
	prev_pos = state.pos
	if go_down and state.pos < 30:
		state.pos += 1
		move_z(ft, True)
	elif not go_down and state.pos > 0:
		state.pos -= 1
		move_z(ft, False)
	if prev_pos == 0 and state.pos > 0:
		print(f'BYEWAVE: Starting movement (pos={state.pos})')
	elif prev_pos > 0 and state.pos == 0:
		print('BYEWAVE: Stopping movement')


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
