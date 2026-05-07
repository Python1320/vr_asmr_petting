import ctypes
import logging
import os
import sys
import tkinter as tk
import tkinter.ttk as ttk
import traceback
import webbrowser


HELP_URL = ''
PROGRAMNAME = ''


def exit(n=1):
	if n != 0:
		logging.error('Exiting forcefully {n}..')
	else:
		logging.info('Exiting (no error)...')
	os._exit(n)


def set_help_url(url):
	global HELP_URL
	HELP_URL = url


def set_program_name(name):
	global PROGRAMNAME
	PROGRAMNAME = name


class TopErrorWindow(tk.Tk):
	def __init__(self, title, message, detail, HELP_URL=''):  # noqa: N803
		super().__init__()
		self.details_expanded = True
		self.title(title)
		self.HELP_URL = HELP_URL or globals()['HELP_URL']  # TODO: UUHHHH
		self.geometry('600x450')
		self.minsize(600, 450)
		self.resizable(True, True)
		self.rowconfigure(0, weight=0)
		self.rowconfigure(1, weight=1)
		self.columnconfigure(0, weight=1)

		button_frame = tk.Frame(self)
		button_frame.grid(row=0, column=0, sticky='nsew')
		button_frame.columnconfigure(0, weight=1)
		button_frame.columnconfigure(1, weight=1)

		text_frame = tk.Frame(self)
		text_frame.grid(row=1, column=0, padx=(7, 7), pady=(7, 7), sticky='nsew')
		text_frame.rowconfigure(0, weight=1)
		text_frame.columnconfigure(0, weight=1)

		txt = tk.Text(button_frame, height=1, borderwidth=0)
		txt.grid(row=0, column=0, columnspan=3, pady=(7, 7), padx=(7, 7), sticky='w')
		txt.insert('1.0', message)

		ttk.Button(button_frame, text='Exit', command=self.destroy).grid(row=1, column=1, sticky='e')
		if self.HELP_URL:
			ttk.Button(
				button_frame,
				text='Help',
				command=lambda: webbrowser.open_new_tab(self.HELP_URL),
			).grid(row=1, column=2, padx=(7, 7), sticky='e')

		self.textbox = tk.Text(text_frame, height=6)
		self.textbox.insert('1.0', detail)
		self.textbox.config(state='disabled')
		self.scrollb = tk.Scrollbar(text_frame, command=self.textbox.yview)
		self.textbox.config(yscrollcommand=self.scrollb.set)
		self.textbox.grid(row=0, column=0, sticky='nsew')
		self.scrollb.grid(row=0, column=1, sticky='nsew')
		self.mainloop()


def fatal(msg, detail=None, nodecor=False):
	if 'debugpy' in sys.modules:
		raise  # Exception(str(msg))

	# if os.name == 'nt':
	# ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), 'vr_audience_fire - ERROR', 0)
	# else:
	# print(msg)

	title = f'{PROGRAMNAME or os.getenv("PROGRAMNAME", "VRApp")}: Error'
	message = str(msg) if nodecor else 'An error has occured, sorry about that.\n\nDetails: ' + str(msg)
	detail = detail or traceback.format_exc()
	TopErrorWindow(title, message, detail)

	logging.error(traceback.format_exc())
	exit()


def set_console_title(title: str, printit=False):
	# TODO: console.utils.set_title(terminal_title)
	if os.name == 'nt':
		ctypes.windll.kernel32.SetConsoleTitleW(title or PROGRAMNAME)
	else:
		print(f'\033]0;{title}\a', end='', flush=True)
	if printit:
		print(f'{Fore.CYAN}{title}{Style.RESET_ALL}')


# print(Path(__file__).parent, Path(sys.prefix), EXEDIR)

shown_console = False


def show_console():
	# TODO: windows only
	global shown_console
	has_console = False  # TODO: fix has_console
	if shown_console or has_console:
		return
	shown_console = True
	ctypes.windll.kernel32.AllocConsole()
	sys.stdout = open('CONOUT$', 'w')  # noqa: SIM115
	sys.stderr = open('CONOUT$', 'w')  # noqa: SIM115


if __name__ == '__main__':
	show_console()
	logging.error('This is a utility module, not meant to be run directly.')
	print('Please run the main script instead.')
	TopErrorWindow(
		'test title',
		'test message',
		"""These are some details\nnewline\nmore details""",
	)
	input('Press Enter to exit...')
