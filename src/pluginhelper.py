from typing import Any, Awaitable, Callable
import asyncio
import config_reader
from pythonosc.udp_client import SimpleUDPClient

TYPE_CONF = config_reader.AppConfig
TYPE_VRC = SimpleUDPClient
TYPE_MAIN_LOOP = asyncio.AbstractEventLoop
TYPE_TASK_GROUP = asyncio.TaskGroup | None
TYPE_PLUGIN_CONF = config_reader.PluginData


class VRPlugin:
	@staticmethod
	async def on_load(
		conf: TYPE_CONF,
		vrc: TYPE_VRC,
		main_loop: TYPE_MAIN_LOOP,
		task_group: TYPE_TASK_GROUP = None,
	) -> bool:
		return False

	@staticmethod
	async def on_vr(vr=None, controllers=None):
		pass

	@staticmethod
	async def on_start():
		pass


plugin_tick_callbacks: dict[str, Callable[[float, float, Any], Awaitable[Any]]] = {}
_osc_dispatcher: Any = None


def set_osc_dispatcher(disp):
	global _osc_dispatcher
	_osc_dispatcher = disp


def get_osc_dispatcher():
	return _osc_dispatcher


def register_plugin_tick_callback(plugin_name: str, callback: Callable):
	plugin_tick_callbacks[plugin_name] = callback


def register_osc_handler(path: str, handler: Callable):
	if _osc_dispatcher:
		_osc_dispatcher.map(path, handler)
