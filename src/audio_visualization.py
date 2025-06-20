channel_l = False
channel_r = False


def init():
	import pygame

	global channel_l, channel_r, sound_l, sound_r
	pygame.init()
	pygame.mixer.init()
	sound_r = pygame.mixer.Sound('pettingloop_bad.wav')
	sound_l = pygame.mixer.Sound('pettingloop_bad.wav')

	channel_l = pygame.mixer.find_channel()
	channel_l.set_volume(0.0, 0.0)
	channel_l.play(sound_l, loops=-1, fade_ms=100)

	channel_r = pygame.mixer.find_channel()
	channel_r.set_volume(0.0, 0.0)
	channel_r.play(sound_r, loops=-1, fade_ms=100)


def set_volumes(l, r):
	if not channel_r:
		return
	channel_l.set_volume(l, 0.0)  # type: ignore
	channel_r.set_volume(0.0, r)  # type: ignore


def set_volume_l(l):
	if not channel_r:
		return
	channel_l.set_volume(l, 0.0)  # type: ignore


def set_volume_r(r):
	if not channel_r:
		return
	channel_r.set_volume(0.0, r)  # type: ignore


if __name__ == '__main__':
	import pygame

	set_volumes(1, 0)
	while True:
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				pygame.quit()
