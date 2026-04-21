import logging
from utils import find_asset

# Debug sound filenames
ogg_r = 'debugsoundloop_r.ogg'
ogg_l = 'debugsoundloop_l.ogg'

channel_l = None
channel_r = None

log = logging.getLogger(__name__)


def init():
	import pygame
	# We don't want to import pygame unless we have to, since it takes a lot of RAM

	global channel_l, channel_r, sound_l, sound_r
	pygame.init()
	pygame.mixer.init()

	r_path = find_asset(ogg_r)
	l_path = find_asset(ogg_l)

	if not r_path or not l_path:
		log.error('Failed to find sound files.')
		return

	try:
		sound_r = pygame.mixer.Sound(r_path)
		sound_l = pygame.mixer.Sound(l_path)
	except pygame.error:
		log.error('Failed to load sound files.')
		return

	channel_l = pygame.mixer.find_channel()
	channel_l.set_volume(0.0, 0.0)
	channel_l.play(sound_l, loops=-1, fade_ms=100)

	channel_r = pygame.mixer.find_channel()
	channel_r.set_volume(0.0, 0.0)
	channel_r.play(sound_r, loops=-1, fade_ms=100)


def set_volume_l(l: float):
	if not channel_r:
		return
	channel_l.set_volume(l, 0.0)  # type: ignore


def set_volume_r(r: float):
	if not channel_r:
		return
	channel_r.set_volume(0.0, r)  # type: ignore


if __name__ == '__main__':
	import pygame

	init()
	print('playing...')
	set_volume_l(1.0)
	set_volume_r(0.2)
	while True:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				pygame.quit()
