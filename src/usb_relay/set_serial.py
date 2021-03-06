#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Software License Agreement (BSD License)
#
# Copyright (c) 2020, Ben Schattinger
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the names of the authors nor the names of their
#    affiliated organizations may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import division, print_function
from __future__ import unicode_literals

from sys import stderr
from threading import Thread
from sys import version_info
if __name__ == '__main__':
	if __package__ is None:
		import sys
		from os import path
		sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
		from usb_relay import Relay
	else:
		from . import Relay
import time
import hid
import atexit

try:
	from typing import Dict, List
except ImportError:
	pass
try:
	input = raw_input
except NameError:
	pass


class AnsiEscapes:
	HIDE_CURSOR = '\x1b[?25l'
	SHOW_CURSOR = '\x1b[?25h'
	CYAN = "\033[0;36m"
	GREEN = "\033[0;32m"
	RED = "\033[0;31m"
	END = "\033[0m"


class Infinite(object):
	file = stderr
	check_tty = True
	hide_cursor = True
	phases = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

	def __init__(self, message=''):
		self.index = 0
		self.ended = False
		self.message = message

		if self.file and self.is_tty():
			if self.hide_cursor:
				print(AnsiEscapes.HIDE_CURSOR, end='', file=self.file)
			atexit.register(self.finish)
			print(self.message, end='', file=self.file)
			self.file.flush()
		else:
			print(self.message)

	def update(self):
		i = self.index % len(self.phases)
		self.write(AnsiEscapes.CYAN + self.phases[i] + AnsiEscapes.END)

	def clearln(self):
		if self.file and self.is_tty():
			print('\r\x1b[K', end='', file=self.file)

	def write(self, s):
		if self.file and self.is_tty():
			line = s + " " + self.message
			print('\r' + line, end='', file=self.file)
			self.file.flush()

	def writeln(self, line):
		if self.file and self.is_tty():
			self.clearln()
			print(line, end='', file=self.file)
			self.file.flush()

	def finish(self, message=None):
		if self.ended:
			return
		self.ended = True
		if self.file and self.is_tty():
			self.writeln(message if message else "  " + self.message)
			print(file=self.file)
			if self.hide_cursor:
				print(AnsiEscapes.SHOW_CURSOR, end='', file=self.file)
			try:
				atexit.unregister(self.finish)
			except AttributeError:
				pass
		elif message:
			print(message)

	def succeed(self, message=None):
		self.finish(message=AnsiEscapes.GREEN + "✔" + AnsiEscapes.END + " " + (message if message else self.message))

	def is_tty(self):
		try:
			return self.file.isatty() if self.check_tty else True
		except AttributeError:
			return False

	def next(self, n=1):
		self.index = self.index + n
		self.update()


class FindThread(Thread):
	device = None  # type: Relay or None

	def __init__(self, vendor=0x16c0, product=0x05df):
		Thread.__init__(self)
		self.device = None
		self.vendor = vendor
		self.product = product
		self.daemon = True

	def run(self):
		devices = []
		for device in hid.enumerate(self.vendor, self.product):
			devices.append(device["path"])
		while True:
			new_devices = []
			for new_device in hid.enumerate(self.vendor, self.product):
				if new_device["path"] not in devices:
					d = hid.device()
					d.open_path(new_device["path"])
					try:
						relay_count = int(new_device['product_string'][8])
					except IndexError:
						continue
					self.device = Relay(d, relay_count)
					return
				new_devices.append(new_device["path"])
			devices = new_devices
			time.sleep(1)


def prompt(message=''):  # type: (str or unicode) -> str or bytes
	try:
		while True:
			print(message, end=": ")
			if version_info[0] == 2:
				response = bytearray(input())
			else:
				response = input().encode('utf-8')
			if len(response) > 5:
				print(AnsiEscapes.RED + "✖" + AnsiEscapes.END + " Names must be at most 5 bytes")
			else:
				return response
	except EOFError:
		raise KeyboardInterrupt()


if __name__ == '__main__':
	print("Plug in your module. If it is currently plugged in, unplug it and plug it back in.")
	try:
		a = FindThread()
		a.start()
		p = Infinite('Looking for new devices...')
		while a.is_alive():
			p.next()
			time.sleep(1 / 15)
		name = a.device.get_name()
		relay_count = a.device.relay_count
		p.succeed("Found a module named \"{}\" with {} relay{}".format(
			name.decode('utf-8', 'replace'),
			relay_count,
			'' if relay_count == 1 else 's'
		))
		new_name = prompt(message="Enter the new name")
		a.device.set_name(new_name)
		print(AnsiEscapes.GREEN + "✔" + AnsiEscapes.END + " successfully set the name!")
	except KeyboardInterrupt:
		pass
