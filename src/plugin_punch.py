import openvr

import pluginhelper
import logging
from vrappcommon.task_helper import spawn_task

log = logging.getLogger('plugin_punch')

NAME = 'punch'
"""Get punched with contact receiver attack_front 
via OSC /avatar/parameters/attack_front boolean true to move backwards via playspace move (move_x) """


class State:
	pos = 0
	end_time = 0
	cooldown_end_time = 0
	first_trigger: str | None = None
	attack_front = False
	attack_back = False


state = State()


async def on_attack_front(value: bool):
	state.attack_front = value


async def on_attack_back(value: bool):
	state.attack_back = value


async def on_tick(now, ft, poses):
	if state.cooldown_end_time > now:
		return

	has_front = state.attack_front
	has_back = state.attack_back

	if (has_front or has_back) and now < state.end_time:
		move_direction(ft, state.first_trigger == 'front')
	elif (has_front or has_back) and now >= state.end_time:
		if has_front and not has_back:
			state.first_trigger = 'front'
		elif has_back and not has_front:
			state.first_trigger = 'back'
		elif has_front and has_back:
			state.first_trigger = None

		if state.first_trigger:
			state.end_time = now + 2
			state.cooldown_end_time = now + 4
			direction = 'forward' if state.first_trigger == 'front' else 'backward'
			print(f'PUNCH: Punching {direction} for 2 seconds')
	elif state.end_time > 0 and now < state.end_time:
		move_direction(ft, state.first_trigger == 'front')
	elif state.end_time > 0 and now >= state.end_time:
		state.end_time = 0
		state.first_trigger = None


def move_direction(ft, go_forward):
	prev_pos = state.pos
	if go_forward and state.pos < 30:
		state.pos += 1
		move_x(ft, True)
	elif not go_forward and state.pos < 30:
		state.pos += 1
		move_x(ft, False)
	elif not go_forward and state.pos > 0:
		state.pos -= 1
		move_x(ft, True)
	elif go_forward and state.pos > 0:
		state.pos -= 1
		move_x(ft, False)
	if prev_pos == 0 and state.pos > 0:
		print(f'PUNCH: Starting movement (pos={state.pos})')
	elif prev_pos > 0 and state.pos == 0:
		print('PUNCH: Stopping movement')


def move_x(ft, goforward=False):
	print(f'MOVING {"FORWARD" if goforward else "BACKWARD"} (ft={ft:.2f}s)')
	openvr.VRChaperoneSetup().revertWorkingCopy()
	standing_zero_to_raw_tracking_pose = openvr.VRChaperoneSetup().getWorkingStandingZeroPoseToRawTrackingPose()
	pose = standing_zero_to_raw_tracking_pose[1]
	MOVESZ = 0.1
	pose[0][3] += goforward and (MOVESZ) or -MOVESZ
	openvr.VRChaperoneSetup().setWorkingStandingZeroPoseToRawTrackingPose(pose)
	openvr.VRChaperoneSetup().commitWorkingCopy(openvr.EChaperoneConfigFile_Live)


async def on_load(
	conf: pluginhelper.TYPE_CONF,
	vrc: pluginhelper.TYPE_VRC,
	main_loop: pluginhelper.TYPE_MAIN_LOOP,
	task_group: pluginhelper.TYPE_TASK_GROUP = None,
):
	plugin_conf = conf.plugins.get(NAME)

	if not plugin_conf:
		return False

	if not plugin_conf.enabled:
		return False

	pluginhelper.register_plugin_tick_callback(NAME, on_tick)

	disp = pluginhelper.get_osc_dispatcher()
	if not disp:
		return False

	attack_front_path = getattr(plugin_conf, 'attack_front', None)
	attack_back_path = getattr(plugin_conf, 'attack_back', None)

	def wrap(cb):
		def _wrapper(key, *val):
			spawn_task(
				cb(bool(val[0])),
				loop=task_group or main_loop,
				name=f'{NAME}_osc_{cb.__name__}',
			)

		return _wrapper

	if attack_front_path:
		disp.map(attack_front_path, wrap(on_attack_front))
	else:
		log.warning(f'No attack_front OSC path in config for {NAME}')
	if attack_back_path:
		disp.map(attack_back_path, wrap(on_attack_back))
	else:
		log.warning(f'No attack_back OSC path in config for {NAME}')

	return True


async def on_vr(vr=None, controllers=None):
	state.controllers = controllers  # type: ignore


async def on_start():
	return
