# TODO
from pythonosc.udp_client import SimpleUDPClient


class VRChatUDP(SimpleUDPClient):
	def __init__(self, address: str, port: int):
		super().__init__(address, port)


# tap disable on move fwd joystick
