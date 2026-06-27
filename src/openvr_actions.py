import asyncio
import json
import logging

import openvr
from vrappcommon.openvrutils import get_vr_system
from vrappcommon.task_helper import spawn_task
from vrappcommon.jankyguihelpers import fatal

from utils import EXEDIR

log = logging.getLogger('controller')


class ActionHandle:
	def __init__(self, path: str):
		self.path = path
		self._openvr_handle = None

	@property
	def name(self):
		return self.path.rsplit('/', 1)[-1]

	def get_digital(self):
		if self._openvr_handle is None:
			self._openvr_handle = openvr.VRInput().getActionHandle(self.path)
		return openvr.VRInput().getDigitalActionData(self._openvr_handle, openvr.k_ulInvalidInputValueHandle)


# Global state: path -> bState (bool)
state: dict[str, bool] = {}

# Path -> list of async callbacks
_listeners: dict[str, list] = {}

_handles: dict[str, ActionHandle] = {}


def get_handle(path: str) -> ActionHandle:
	if path not in _handles:
		_handles[path] = ActionHandle(path)
	return _handles[path]


def listen(handle: ActionHandle, callback):
	if handle.path not in _listeners:
		_listeners[handle.path] = []
	_listeners[handle.path].append(callback)


async def reg_openvr_actions(loop, task_group: asyncio.TaskGroup | None = None):
	log.info('Registering OpenVR actions...')
	try:
		_vr_system = await get_vr_system(openvr.VRApplication_Overlay, loop=loop, task_group=task_group)
		action_manifest_path = str((EXEDIR / 'actions.json').resolve())
		log.info('Registering action manifest: %s', action_manifest_path)

		error = openvr.VRInput().setActionManifestPath(action_manifest_path)
		if error is not None and error != 0:
			log.error(f'Error setting action manifest path: {action_manifest_path}, OpenVR Error: {error}')

		with open(action_manifest_path, 'r') as f:
			actions_json = json.load(f)
		print(f'Actions from actions.json: {actions_json.get("actions", [])}')

		for action_def in actions_json.get('actions', []):
			path = action_def['name']
			handle = get_handle(path)
			handle._openvr_handle = openvr.VRInput().getActionHandle(path)
			if handle._openvr_handle is None:
				log.error(f'Error getting action handle: {path}')
			else:
				log.info(f'Got action handle: {path} -> {handle._openvr_handle}')

		action_set_handle = openvr.VRInput().getActionSetHandle('/actions/default')
		if action_set_handle is None:
			log.error('Error getting action set handle: /actions/default')

		if not _handles or action_set_handle is None:
			log.error('Failed to get action handles, not starting polling')
		else:
			spawn_task(
				poll_openvr_actions(_vr_system, action_set_handle),
				loop=task_group,
				name='poll_openvr_actions',
			)

	except Exception as e:
		fatal(str(e))


async def poll_openvr_actions(_vr_system, action_set_handle):
	prev_states: dict[str, bool | None] = {}

	for path in _handles:
		prev_states[path] = None

	try:
		pass  # openvr.VRInput().openBindingUI('', action_set, 0, True)
	except Exception as e:
		log.error(f'Error opening binding UI: {e}')

	while True:
		active_action_sets = (openvr.VRActiveActionSet_t * 1)()
		active_action_set = active_action_sets[0]
		active_action_set.ulActionSet = action_set_handle
		openvr.VRInput().updateActionState(active_action_sets)

		for path, handle in list(_handles.items()):
			try:
				digital_data = handle.get_digital()
			except openvr.error_code.InputError_InvalidHandle:
				continue

			state[path] = bool(digital_data.bState)

			prev = prev_states.get(path)
			if prev is not None and prev != digital_data.bState:
				log.debug(f'{handle.name}: bState={digital_data.bState}, bActive={digital_data.bActive}')
			prev_states[path] = digital_data.bState

			if path in _listeners:
				for cb in _listeners[path]:
					await cb(handle)

		await asyncio.sleep(0.1)
