# TODO
import asyncio
import logging
import os
import time

from aiohttp import web
import openvr
from psutil import process_iter
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
from zeroconf import NonUniqueNameException

from vrappcommon.jankyguihelpers import fatal
from vrchat_oscquery.common import _create_service_info, _get_app_host, _oscjson_response, _unused_port
from zeroconf.asyncio import AsyncZeroconf


class VRChatUDP(SimpleUDPClient):
	def __init__(self, address: str, port: int):
		super().__init__(address, port)


class VRCOSCClient:
	osc_port: int = -1
	osc_host: str = ''
	http_port: int = -1

	def __init__(self, osc_port: int = -1, osc_host: str = '', http_port: int = -1):
		self.osc_host = osc_host
		self.osc_port = osc_port
		self.http_port = http_port


def is_vrchat_running() -> bool:
	_proc_name = 'VRChat.exe' if os.name == 'nt' else 'VRChat'
	return _proc_name in (p.name() for p in process_iter())


# Custom version of vrc_osc with VRC bugfix and returning params
async def vrc_osc(name: str, dispatcher: Dispatcher, foreground=False, zeroconf=True):
	osc_port = _unused_port()
	http_port = _unused_port()
	host = _get_app_host()

	await AsyncIOOSCUDPServer((host, osc_port), dispatcher, asyncio.get_event_loop()).create_serve_endpoint()  # type: ignore
	if zeroconf:
		app = web.Application()
		last_root_requested = time.monotonic() + 5
		last_hinfo_requested = time.monotonic() + 5

		def req_handler(req):
			nonlocal last_root_requested, last_hinfo_requested
			request_path = req.path_qs
			if request_path == '/':
				if time.monotonic() - last_root_requested < 1:
					logging.debug('BUGFIX: Too many requests to root path, throttling due to BUG.')
					return web.Response(status=404, body='Too many requests, please wait a moment.')
				last_root_requested = time.monotonic()
			elif request_path == '/?HOST_INFO':
				if time.monotonic() - last_hinfo_requested < 1:
					logging.debug('BUGFIX: Too many requests to HOST_INFO, throttling due to BUG.')
					return web.Response(status=404, body='Too many requests, please wait a moment.')
				last_hinfo_requested = time.monotonic()

			return web.Response(body=_oscjson_response(req.path_qs, osc_port))

		app.add_routes([web.get('/', req_handler)])  # type: ignore
		runner = web.AppRunner(app)
		await runner.setup()
		await web.TCPSite(runner, host, http_port).start()

		try:
			await AsyncZeroconf().async_register_service(_create_service_info(name, http_port))
		except NonUniqueNameException:
			fatal(
				'Another instance of this program is already running!',
				detail='Another instance of this program is already running (zeroconf name conflict). If you are sure that this is not the case, wait a moment and try again.',
				nodecor=True,
			)
			exit(1)

	if foreground:
		await asyncio.gather(*asyncio.all_tasks())

	client = VRCOSCClient(osc_port=osc_port, osc_host=host, http_port=http_port)
	return client
