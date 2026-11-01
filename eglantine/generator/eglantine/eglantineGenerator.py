from __future__ import annotations

from typing import TYPE_CHECKING

from ... import Command
from ..Generator import Generator

if TYPE_CHECKING:
    from ...types import HotkeysContext


class EglantineGenerator(Generator):

    def getHotkeysContext(self) -> HotkeysContext:
        return {
            "name": "eglantine",
            "keys": { "exit": ["KEY_LEFTALT", "KEY_F4"] }
        }

    def generate(self, system, rom, playersControllers, metadata, guns, wheels, gameResolution):
        # eglantine-launch.sh finds the game's exefs/main inside its .sw2 folder
        # and logs to /userdata/system/logs/eglantine.log
        commandArray = ['/userdata/system/add-ons/eglantine/eglantine-launch.sh', str(rom)]

        return Command.Command(array=commandArray, env={})
