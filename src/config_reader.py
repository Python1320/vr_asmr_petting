import functools
import json

# vrchat_oscquery provides zeroconf

import logging
import sys
from utils import fatal, EXEDIR


from typing import Any, Tuple, Type

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, JsonConfigSettingsSource


class DatabaseJsonSettings(BaseModel):
	postgres_user: str
	postgres_password: str
	postgres_host: str
	postgres_port: int
	postgres_db: str


conflocation = EXEDIR / 'config.json'

try:
	with conflocation.open('r') as f:
		conf_json = json.load(f)
except FileNotFoundError as e:
	fatal(f'Configuration file missing! Location: {conflocation}')
except json.JSONDecodeError as e:
	fatal(f'Config file malformed! Check syntax for example with https://jsonlint.com/ \n Error: {e}')


class Senders(BaseModel):
	volume_left: str | None = None
	volume_right: str | None = None
	sound_taps_right: str | None = None
	sound_taps_left: str | None = None
	model_config = ConfigDict(extra='forbid')


class PluginData(BaseModel):
	enabled: bool = False
	description: str | None = None
	model_config = ConfigDict(extra='allow')


class AppConfig(BaseSettings):
	model_config = SettingsConfigDict(json_file=conflocation)
	senders: Senders = Senders()
	vrc_osc_port: int = 9000
	vrc_osc_ip: str = '127.0.0.1'
	osc_detectors: dict[str, str] | None = None
	zeroconf: bool = True
	plugins: dict[str, PluginData] = {}
	debug: bool = False
	install_to_steamvr: bool = True

	@classmethod
	def settings_customise_sources(
		cls,
		settings_cls: Type[BaseSettings],
		init_settings: PydanticBaseSettingsSource,
		env_settings: PydanticBaseSettingsSource,
		dotenv_settings: PydanticBaseSettingsSource,
		file_secret_settings: PydanticBaseSettingsSource,
	) -> Tuple[PydanticBaseSettingsSource, ...]:
		return (JsonConfigSettingsSource(settings_cls),)


@functools.cache
def get_config():
	try:
		conf = AppConfig()
	except ValidationError as e:
		fatal(f'Config file invalid! Check below for details!', detail=str(e), nodecor=True)

	if not conf.zeroconf:
		logging.warning('Zeroconf is disabled, warranty void!')

	logging.debug(f'Config loaded from {conflocation}:')
	if 'debugpy' not in sys.modules:
		logging.debug(json.dumps(conf.model_dump(), indent='\t'))
	return conf


def save_config(conf: AppConfig):
	try:
		with conflocation.open('w') as f:
			json.dump(conf.model_dump(), f, indent='\t', ensure_ascii=False, sort_keys=True)
			f.flush()
			logging.debug(f'Config saved to {conflocation}:')
			logging.debug(json.dumps(conf.model_dump(), indent='\t'))
	except Exception as e:
		logging.error(f'Failed to save config: {e}')
	else:
		logging.info(f'Config saved to {conflocation}')


if __name__ == '__main__':
	# For testing purposes
	conf = get_config()
	print(conf)
	save_config(conf)
