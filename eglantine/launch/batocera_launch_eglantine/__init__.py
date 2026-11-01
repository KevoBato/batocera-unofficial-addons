from __future__ import annotations

from batocera_common.dataclasses import cached_dataclass, cached_property
from batocera_launch import Command, Emulator, HotkeysContext


# batocera-launch emulator for Eglantine (Batocera 44 and later, which have no
# configgen). The installer registers it as the "eglantine" entry point.
@cached_dataclass
class Eglantine(Emulator):

    @cached_property
    def hotkeygen_context(self) -> HotkeysContext:
        return {
            'name': 'eglantine',
            'keys': {'exit': ['KEY_LEFTALT', 'KEY_F4']},
        }

    async def configure(self) -> Command:
        # eglantine-launch.sh finds the game's exefs/main inside its .sw2 folder
        # and logs to /userdata/system/logs/eglantine.log
        return Command(['/userdata/system/add-ons/eglantine/eglantine-launch.sh', self.rom])
