from constantly import NamedConstant
from zope.interface import provider
from twisted.logger import ILogObserver, formatEvent, LogEvent, LogLevel

@provider(ILogObserver)
class LevelObserver:

    def __init__(self, level: str | NamedConstant = 'info'):
        if isinstance(level, str):
            level = level.lower()
            if level == 'warning':
                level = 'warn'
            level = LogLevel.levelWithName(level)
        self._level = level

    def __call__(self, event: LogEvent) -> None:
        event_level = event.get('log_level', None)
        if event_level >= self._level:
            print(formatEvent(event))
