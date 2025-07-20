import shutil
from cx_Freeze import setup, Executable

packages = ['pythonosc', 'psutil', 'zeroconf', 'json', 'threading', 'time', 'os', 'sys', 'ctypes', 'traceback']
file_include = ['config.json', 'app.vrmanifest', '../pettingloop_bad.wav']

build_exe_options = {
	'packages': packages,
	'include_files': file_include,
	'include_msvcr': False,
	'optimize': 0,
	'build_exe': '../vr_asmr_petting_helper',
}

setup(
	name='vr_asmr_petting',
	version='0.2',
	description='vr_asmr_petting.exe: VR OSC ASMR sounds while moving tracked objects',
	options={'build_exe': build_exe_options},
	executables=[
		Executable('main.py', target_name='vr_asmr_petting_console.exe', base='console', icon='../icon.ico'),
		Executable('main.py', target_name='vr_asmr_petting.exe', base='Win32GUI', icon='../icon.ico'),
	],
)

shutil.make_archive('../vr_asmr_petting_helper', 'zip', '../vr_asmr_petting_helper')
