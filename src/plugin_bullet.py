import openvr

import pluginhelper
import asmr_worker

NAME = 'bullet'


class State:
	pos = 0
	active = False
	end_time = 0.0
	cooldown_until = 0.0
	remain_seconds = 10.0
	reactivate_after_remain = 10.0


state = State()


async def on_tick(now, ft, poses):
	if state.active:
		if now >= state.end_time:
			state.active = False
			state.pos = 0
			print('BULLET: Remaining time ended, rising up')
			restore_from_ground()
		return

	if asmr_worker.worker.attacked and now >= state.cooldown_until:
		state.active = True
		state.pos = 1
		state.end_time = now + state.remain_seconds
		state.cooldown_until = state.end_time + state.reactivate_after_remain
		print(f'BULLET: Attacked! Immediate underground for {state.remain_seconds} seconds')
		sink_to_ground()


def adjust_ground_height(delta: float):
	chaperone = openvr.VRChaperoneSetup()
	chaperone.revertWorkingCopy()
	standing_zero_to_raw_tracking_pose = chaperone.getWorkingStandingZeroPoseToRawTrackingPose()
	pose = standing_zero_to_raw_tracking_pose[1]
	pose[1][3] += delta
	chaperone.setWorkingStandingZeroPoseToRawTrackingPose(pose)
	chaperone.commitWorkingCopy(openvr.EChaperoneConfigFile_Live)


def sink_to_ground():
	SINK_DEPTH = 3.0
	adjust_ground_height(SINK_DEPTH)


def restore_from_ground():
	SINK_DEPTH = 3.0
	adjust_ground_height(-SINK_DEPTH)


async def on_load(conf: pluginhelper.TYPE_CONF, vrc: pluginhelper.TYPE_VRC, main_loop: pluginhelper.TYPE_MAIN_LOOP):
	plugin_conf = conf.plugins.get(NAME)

	if not plugin_conf:
		return False

	if not plugin_conf.enabled:
		return False

	state.remain_seconds = getattr(plugin_conf, 'remain_seconds', state.remain_seconds)
	state.reactivate_after_remain = getattr(plugin_conf, 'reactivate_after_remain', None) or getattr(
		plugin_conf, 'reactivat_after_remain', state.reactivate_after_remain
	)

	pluginhelper.register_plugin_tick_callback(NAME, on_tick)
	return True


async def on_vr(vr=None, controllers=None):
	state.controllers = controllers  # type: ignore


async def on_start():
	return  # we run on tick
