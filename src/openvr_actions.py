import asyncio
import json
import logging

import openvr
from vrappcommon.openvrutils import get_vr_system
from vrappcommon.task_helper import spawn_task
from vrappcommon.jankyguihelpers import fatal

import asmr_worker
from utils import EXEDIR

log = logging.getLogger('vr_asmr_petting.openvr_actions')


async def reg_openvr_actions(loop=False):
	log.info('Registering OpenVR actions...')
	try:
		_vr_system = await get_vr_system(openvr.VRApplication_Overlay, loop=loop)
		action_manifest_path = str((EXEDIR / 'actions.json').resolve())
		log.info('Registering action manifest: %s', action_manifest_path)

		error = openvr.VRInput().setActionManifestPath(action_manifest_path)
		if error is not None and error != 0:
			log.error(f'Error setting action manifest path: {action_manifest_path}, OpenVR Error: {error}')

		with open(action_manifest_path, 'r') as f:
			actions_json = json.load(f)
		print(f'Actions from actions.json: {actions_json.get("actions", [])}')

		action_handle_left = openvr.VRInput().getActionHandle('/actions/default/in/TouchLeft')
		if action_handle_left is None:
			log.error('Error getting action handle: /actions/default/in/TouchLeft')
		action_handle_right = openvr.VRInput().getActionHandle('/actions/default/in/TouchRight')
		if action_handle_right is None:
			log.error('Error getting action handle: /actions/default/in/TouchRight')
		action_set_handle = openvr.VRInput().getActionSetHandle('/actions/default')
		if action_set_handle is None:
			log.error('Error getting action set handle: /actions/default')

		log.info(f'Action handles: left={action_handle_left}, right={action_handle_right}, set={action_set_handle}')

		if action_handle_left is None or action_handle_right is None or action_set_handle is None:
			log.error('Failed to get action handles, not starting polling')
		else:
			spawn_task(
				poll_openvr_actions(_vr_system, action_handle_left, action_handle_right),
				name='poll_openvr_actions',
			)

	except Exception as e:
		fatal(str(e))


async def poll_openvr_actions(_vr_system, action_handle_left, action_handle_right):
	prev_states = {action_handle_left: None, action_handle_right: None}

	action_set = openvr.VRInput().getActionSetHandle('/actions/default')
	try:
		pass  # openvr.VRInput().openBindingUI('', action_set, 0, True)
	except Exception as e:
		log.error(f'Error opening binding UI: {e}')

	while True:
		active_action_sets = (openvr.VRActiveActionSet_t * 1)()
		active_action_set = active_action_sets[0]
		active_action_set.ulActionSet = action_set
		openvr.VRInput().updateActionState(active_action_sets)

		actions = [
			(action_handle_left, 'TouchLeft'),
			(action_handle_right, 'TouchRight'),
		]
		for handle, name in actions:
			try:
				state = openvr.VRInput().getDigitalActionData(handle, openvr.k_ulInvalidInputValueHandle)
			except openvr.error_code.InputError_InvalidHandle:
				continue

			if prev_states.get(handle) is not None and prev_states[handle] != state.bState:
				print(f'{name}: bState={state.bState}, bActive={state.bActive}')
			prev_states[handle] = state.bState

			if name == 'TouchLeft':
				await asmr_worker.worker.set_arm_touch_state('left', bool(state.bState))
			elif name == 'TouchRight':
				await asmr_worker.worker.set_arm_touch_state('right', bool(state.bState))

		await asyncio.sleep(0.1)
