from typing import Any, Awaitable, Callable
import config_reader
from pythonosc.udp_client import SimpleUDPClient
import asyncio

TYPE_CONF = config_reader.AppConfig
TYPE_VRC = SimpleUDPClient
TYPE_MAIN_LOOP = asyncio.AbstractEventLoop
TYPE_PLUGIN_CONF = config_reader.PluginData


class VRPlugin:
	@staticmethod
	async def on_load(conf: TYPE_CONF, vrc: TYPE_VRC, main_loop: TYPE_MAIN_LOOP) -> bool:
		return False

	@staticmethod
	async def on_vr(vr=None, controllers=None):
		pass

	@staticmethod
	async def on_start():
		pass


plugin_tick_callbacks: dict[str, Callable[[float, float, Any], Awaitable[Any]]] = {}


def register_plugin_tick_callback(plugin_name: str, callback: Callable):
	plugin_tick_callbacks[plugin_name] = callback
