import openvr
import math
import numpy
import time

import pluginhelper
import asmr_worker

NAME = 'purr'


""""
Start purring if calmed down for 5 seconds and received headpats for 3 seconds, stop purring if rapid controller/head movement/twisting or moving around.
Also no purring if standing (how to determine?)
vrc.sendOSC("/avatar/parameters/purring", true) to start purring (fading handled in avatar)
"""


class State:
	calmed_down_time = 0
	purring = False


state = State()


async def on_tick(now, ft, poses):
	pass


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
	return
