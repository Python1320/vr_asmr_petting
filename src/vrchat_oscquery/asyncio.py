import asyncio
from aiohttp import web
from zeroconf.asyncio import AsyncZeroconf
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
from .common import _unused_port, _oscjson_response, _create_service_info, _get_app_host


async def vrc_osc(name: str, dispatcher: Dispatcher, foreground=False):
	osc_port = _unused_port()
	http_port = _unused_port()
	host = _get_app_host()

	await AsyncZeroconf().async_register_service(_create_service_info(name, http_port))

	await AsyncIOOSCUDPServer((host, osc_port), dispatcher, asyncio.get_event_loop()).create_serve_endpoint()

	app = web.Application()

	def req_handler(req):
		return web.Response(body=_oscjson_response(req.path_qs, osc_port))

	app.add_routes([web.get('/', req_handler)])
	runner = web.AppRunner(app)
	await runner.setup()
	await web.TCPSite(runner, host, http_port).start()

	if foreground:
		await asyncio.gather(*asyncio.all_tasks())
