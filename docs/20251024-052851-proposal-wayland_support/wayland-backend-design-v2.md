# Технический дизайн: Backend-абстракция для поддержки Wayland (v2)

**Дата:** 24 октября 2025  
**Версия:** 2.0 (исправленная архитектура)  
**Статус:** Техническое предложение

---

## Содержание

1. [Проблема](#проблема)
2. [Цели и ограничения](#цели-и-ограничения)
3. [Архитектурное решение](#архитектурное-решение)
4. [Детальный дизайн](#детальный-дизайн)
5. [План реализации](#план-реализации)
6. [Риски и митигация](#риски-и-митигация)

---

## Проблема

### Текущая ситуация

**Два отдельных приложения:**
1. **tap_detector** - интерактивная утилита для определения комбинаций клавиш
2. **tap_launcher** - daemon для запуска команд по тапам

**Оба используют** библиотеку `pynput` для перехвата событий клавиатуры.

**Проблема:** `pynput` работает только с X11 и не поддерживает Wayland.

### Почему это критично?

- KUbuntu 25.10 использует Wayland по умолчанию
- Оба приложения полностью неработоспособны в Wayland-сессиях
- Переход на Wayland неизбежен для современных Linux-дистрибутивов

---

## Цели и ограничения

### Цели

1. ✅ **Добавить поддержку Wayland** в оба приложения
2. ✅ **Сохранить работу X11** (обратная совместимость)
3. ✅ **Минимизировать изменения** в существующем коде
4. ✅ **Общий код для обоих приложений** (DRY principle)
5. ✅ **Прозрачное переключение** между backend'ами (автоопределение)

### Ключевое требование

**Общий код обработки клавиатуры** должен быть в **отдельном модуле**, используемом обоими приложениями:
- `tap_detector` использует его для отображения нажатых клавиш
- `tap_launcher` использует его для детектирования тапов и запуска команд

---

## Архитектурное решение

### Ключевая идея: Общий модуль `common`

Создать **общий модуль** `src/common/` с backend'ами, который используют оба приложения:

```
src/
├── common/                      # ← ОБЩИЙ КОД
│   ├── __init__.py
│   ├── backends/                # ← Backend'ы клавиатуры
│   │   ├── __init__.py
│   │   ├── base.py             # Абстракция
│   │   ├── pynput_backend.py   # X11 реализация
│   │   ├── evdev_backend.py    # Wayland реализация
│   │   ├── key_mapping.py      # evdev→pynput маппинг
│   │   └── detector.py         # Автоопределение
│   └── key_normalizer.py       # ← ПЕРЕМЕСТИТЬ из tap_detector
│
├── tap_detector/                # ← Приложение 1
│   ├── __init__.py
│   ├── main.py
│   ├── tap_monitor.py          # использует common.backends
│   ├── formatter.py
│   └── constants.py
│
└── tap_launcher/                # ← Приложение 2
    ├── __init__.py
    ├── main.py
    ├── launcher_monitor.py     # использует common.backends
    ├── hotkey_matcher.py
    ├── command_executor.py
    ├── config_loader.py
    ├── daemon_manager.py
    └── models.py
```

### Архитектура использования

```
┌─────────────────────────────────────────┐
│         tap_detector (app 1)           │
│    ┌─────────────────────────────┐     │
│    │    TapMonitor               │     │
│    │  (логика отображения)       │     │
│    └──────────┬──────────────────┘     │
└───────────────┼────────────────────────┘
                │
                │ использует
                │
┌───────────────▼────────────────────────┐
│      src/common/ (ОБЩИЙ КОД)          │
│                                        │
│   ┌────────────────────────────────┐  │
│   │  KeyboardBackend (абстракция)  │  │
│   └────────────┬───────────────────┘  │
│                │                       │
│      ┌─────────┴─────────┐            │
│      │                   │            │
│  ┌───▼──────┐    ┌───────▼──────┐    │
│  │ Pynput   │    │    Evdev     │    │
│  │ Backend  │    │   Backend    │    │
│  │  (X11)   │    │  (Wayland)   │    │
│  └──────────┘    └──────────────┘    │
│                                        │
│   key_normalizer (общие утилиты)      │
└────────────────────────────────────────┘
                │
                │ использует
                │
┌───────────────▼────────────────────────┐
│         tap_launcher (app 2)           │
│    ┌─────────────────────────────┐     │
│    │   LauncherMonitor           │     │
│    │  (логика запуска команд)    │     │
│    └─────────────────────────────┘     │
└────────────────────────────────────────┘
```

---

## Детальный дизайн

### 1. Структура файлов (полная)

```
/home/shtirliz/workspace/myself/tap_launcher/
├── src/
│   ├── common/                          # ← НОВЫЙ: общий код
│   │   ├── __init__.py
│   │   │
│   │   ├── backends/                    # Backend'ы клавиатуры
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Абстракция KeyboardBackend
│   │   │   ├── pynput_backend.py       # X11 реализация
│   │   │   ├── evdev_backend.py        # Wayland реализация
│   │   │   ├── key_mapping.py          # evdev→pynput маппинг
│   │   │   └── detector.py             # Автоопределение backend'а
│   │   │
│   │   └── key_normalizer.py           # ← ПЕРЕМЕСТИТЬ из tap_detector
│   │       # Функции: normalize_key(), format_keys_display()
│   │
│   ├── tap_detector/                    # Приложение 1
│   │   ├── __init__.py
│   │   ├── main.py                     # CLI
│   │   ├── tap_monitor.py              # ИЗМЕНИТЬ: использует common.backends
│   │   ├── formatter.py                # Форматирование вывода
│   │   └── constants.py
│   │
│   └── tap_launcher/                    # Приложение 2
│       ├── __init__.py
│       ├── main.py                     # CLI
│       ├── launcher_monitor.py         # ИЗМЕНИТЬ: использует common.backends
│       ├── hotkey_matcher.py
│       ├── command_executor.py
│       ├── config_loader.py
│       ├── daemon_manager.py
│       └── models.py
│
├── pyproject.toml                       # ИЗМЕНИТЬ: добавить common
├── config/
│   └── tap-launcher.toml.example
├── docs/
│   └── ...
└── README.md
```

### 2. Базовая абстракция (src/common/backends/base.py)

```python
"""Base keyboard backend abstraction.

This module is SHARED between tap_detector and tap_launcher.
Both applications use backends to get keyboard events.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable


class KeyboardBackend(ABC):
    """Abstract interface for keyboard event sources.
    
    A backend is responsible for:
    - Listening to keyboard events from the system
    - Converting events to a unified format (pynput Key/KeyCode objects)
    - Calling callbacks for press/release events
    
    The unified format ensures that both tap_detector and tap_launcher
    can work with the same Key objects regardless of the underlying
    event source (pynput on X11 or evdev on Wayland).
    """
    
    @abstractmethod
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening for keyboard events (blocking).
        
        Args:
            on_press: Callback for key press events
                     Receives pynput Key or KeyCode object
            on_release: Callback for key release events
                       Receives pynput Key or KeyCode object
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop listening for keyboard events."""
        pass
    
    @abstractmethod
    def get_backend_name(self) -> str:
        """Return the name of this backend (for logging)."""
        pass


class BackendNotAvailableError(Exception):
    """Raised when a backend cannot be initialized."""
    pass
```

### 3. PynputBackend (src/common/backends/pynput_backend.py)

```python
"""Pynput-based keyboard backend for X11.

This backend is SHARED between tap_detector and tap_launcher.
"""

import logging
from typing import Any, Callable

from .base import BackendNotAvailableError, KeyboardBackend


class PynputBackend(KeyboardBackend):
    """Keyboard backend using pynput (X11 only)."""
    
    def __init__(self) -> None:
        """Initialize pynput backend."""
        self.logger = logging.getLogger('common.backend.pynput')
        self.listener: Any = None
        
        try:
            import pynput  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'pynput library is not installed'
            ) from e
        
        self.logger.debug('PynputBackend initialized')
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening using pynput."""
        from pynput import keyboard
        
        self.logger.info('Starting pynput keyboard listener (X11)')
        
        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
            suppress=False
        )
        
        self.listener.start()
        self.listener.join()
    
    def stop(self) -> None:
        """Stop the pynput listener."""
        if self.listener:
            self.logger.info('Stopping pynput keyboard listener')
            self.listener.stop()
            self.listener = None
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return 'pynput (X11)'
```

### 4. EvdevBackend (src/common/backends/evdev_backend.py)

```python
"""Evdev-based keyboard backend for Wayland.

This backend is SHARED between tap_detector and tap_launcher.
"""

import logging
import threading
from typing import Any, Callable

from .base import BackendNotAvailableError, KeyboardBackend
from .key_mapping import evdev_to_pynput_key


class EvdevBackend(KeyboardBackend):
    """Keyboard backend using evdev (Wayland/X11)."""
    
    def __init__(self, device_path: str | None = None) -> None:
        """Initialize evdev backend.
        
        Args:
            device_path: Optional path to specific input device
        """
        self.logger = logging.getLogger('common.backend.evdev')
        self.device_path = device_path
        self.device: Any = None
        self._stop_event = threading.Event()
        
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')
    
    def _find_keyboard_device(self) -> Any:
        """Find a keyboard device in /dev/input/."""
        import evdev
        from evdev import ecodes
        
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        except PermissionError as e:
            raise BackendNotAvailableError(
                'Permission denied accessing /dev/input/. '
                'Add user to "input" group: sudo usermod -a -G input $USER'
            ) from e
        
        keyboards = []
        for device in devices:
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if (ecodes.KEY_LEFTCTRL in keys or 
                    ecodes.KEY_RIGHTCTRL in keys or
                    ecodes.KEY_LEFTALT in keys):
                    keyboards.append(device)
                    self.logger.debug(
                        f'Found keyboard: {device.name} at {device.path}'
                    )
        
        if not keyboards:
            raise BackendNotAvailableError('No keyboard device found')
        
        selected = keyboards[0]
        self.logger.info(f'Using keyboard device: {selected.name}')
        return selected
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening using evdev."""
        from evdev import categorize, ecodes
        
        if self.device_path:
            import evdev
            self.device = evdev.InputDevice(self.device_path)
        else:
            self.device = self._find_keyboard_device()
        
        self.logger.info('Starting evdev keyboard listener (Wayland)')
        self._stop_event.clear()
        
        try:
            for event in self.device.read_loop():
                if self._stop_event.is_set():
                    break
                
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    keycode = key_event.keycode
                    
                    try:
                        pynput_key = evdev_to_pynput_key(keycode)
                    except KeyError:
                        self.logger.debug(f'Unknown keycode: {keycode}')
                        continue
                    
                    if key_event.keystate == key_event.key_down:
                        on_press(pynput_key)
                    elif key_event.keystate == key_event.key_up:
                        on_release(pynput_key)
        
        finally:
            pass
    
    def stop(self) -> None:
        """Stop the evdev listener."""
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        
        if self.device:
            self.device.close()
            self.device = None
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return 'evdev (Wayland/X11)'
```

### 5. Key Mapping (src/common/backends/key_mapping.py)

Полный маппинг evdev→pynput ключей (см. предыдущую версию дизайна).

### 6. Backend Detector (src/common/backends/detector.py)

```python
"""Backend detection and factory.

This module is SHARED between tap_detector and tap_launcher.
"""

import logging
import os
from typing import Any

from .base import BackendNotAvailableError, KeyboardBackend
from .evdev_backend import EvdevBackend
from .pynput_backend import PynputBackend


logger = logging.getLogger('common.backend')


def detect_session_type() -> str:
    """Detect current display server type.
    
    Returns:
        str: 'wayland', 'x11', or 'unknown'
    """
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    
    if session_type:
        logger.debug(f'Detected session type: {session_type}')
        return session_type
    
    if os.environ.get('WAYLAND_DISPLAY'):
        logger.debug('Detected Wayland from WAYLAND_DISPLAY')
        return 'wayland'
    
    if os.environ.get('DISPLAY'):
        logger.debug('Detected X11 from DISPLAY')
        return 'x11'
    
    logger.warning('Could not detect session type')
    return 'unknown'


def create_backend(
    backend_name: str | None = None,
    **kwargs: Any
) -> KeyboardBackend:
    """Create appropriate keyboard backend.
    
    Args:
        backend_name: Explicitly specify backend ('pynput', 'evdev', 'auto')
                     If None or 'auto', will auto-detect based on session
        **kwargs: Additional arguments passed to backend constructor
    
    Returns:
        KeyboardBackend: Initialized backend instance
    
    Raises:
        BackendNotAvailableError: If no suitable backend available
    """
    if backend_name is None or backend_name == 'auto':
        session_type = detect_session_type()
        
        if session_type == 'wayland':
            backend_name = 'evdev'
        elif session_type == 'x11':
            backend_name = 'pynput'
        else:
            logger.warning('Unknown session type, trying pynput first')
            backend_name = 'pynput'
    
    if backend_name == 'pynput':
        try:
            backend = PynputBackend(**kwargs)
            logger.info(f'Using backend: {backend.get_backend_name()}')
            return backend
        except BackendNotAvailableError as e:
            logger.warning(f'pynput backend not available: {e}')
            logger.info('Falling back to evdev backend')
            backend_name = 'evdev'
    
    if backend_name == 'evdev':
        try:
            backend = EvdevBackend(**kwargs)
            logger.info(f'Using backend: {backend.get_backend_name()}')
            return backend
        except BackendNotAvailableError as e:
            raise BackendNotAvailableError(
                f'No suitable keyboard backend available. '
                f'Last error: {e}'
            ) from e
    
    raise BackendNotAvailableError(
        f'Unknown backend name: {backend_name}'
    )
```

### 7. Общая утилита (src/common/key_normalizer.py)

```python
"""Key normalization utilities.

This module is SHARED between tap_detector and tap_launcher.
MOVED from tap_detector/key_normalizer.py
"""

from typing import Any


def normalize_key(key: Any) -> str:
    """Normalize pynput Key/KeyCode to string representation.
    
    This function is used by both:
    - tap_detector: for displaying key names
    - tap_launcher: for matching hotkeys
    
    Args:
        key: pynput Key or KeyCode object
    
    Returns:
        str: Normalized key name (e.g., 'ctrl_l', 'a', 'space')
    """
    from pynput import keyboard
    
    # Handle special keys (modifiers, function keys, etc.)
    if isinstance(key, keyboard.Key):
        return key.name
    
    # Handle character keys
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        # Handle keys without char representation
        return f'key_{key.vk}'
    
    return str(key)


def format_keys_display(keys: set[Any]) -> str:
    """Format set of keys for display.
    
    Used by tap_detector for output formatting.
    
    Args:
        keys: Set of pynput Key/KeyCode objects
    
    Returns:
        str: Formatted string (e.g., 'Ctrl+Alt')
    """
    normalized = [normalize_key(key) for key in keys]
    # Capitalize and join with '+'
    return '+'.join(sorted(k.capitalize() for k in normalized))
```

### 8. Интеграция в TapMonitor (tap_detector)

**`src/tap_detector/tap_monitor.py`:**

```python
"""Tap monitoring for tap_detector.

Uses shared backend from common module.
"""

from common.backends.detector import create_backend
from common.backends.base import KeyboardBackend
from common.key_normalizer import normalize_key  # ← ИЗМЕНИТЬ импорт

class TapMonitor:
    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        on_keys_detected: Callable | None = None,
        on_tap_invalid: Callable | None = None,
        check_timer_delay: Callable | None = None,
        backend: KeyboardBackend | None = None,  # ← НОВЫЙ параметр
    ) -> None:
        # ... existing code ...
        
        # Create or use provided backend
        self.backend = backend or create_backend()  # ← НОВОЕ
    
    def start(self) -> None:
        """Start monitoring (uses backend)."""
        self.backend.start(
            on_press=self._on_press,
            on_release=self._on_release
        )
    
    def stop(self) -> None:
        """Stop monitoring."""
        self.backend.stop()
    
    # _on_press и _on_release - БЕЗ ИЗМЕНЕНИЙ!
```

### 9. Интеграция в LauncherMonitor (tap_launcher)

**`src/tap_launcher/launcher_monitor.py`:**

```python
"""Launcher monitoring for tap_launcher.

Uses shared backend from common module.
"""

from common.key_normalizer import format_keys_display  # ← ИЗМЕНИТЬ импорт
from tap_detector.tap_monitor import TapMonitor  # ← TapMonitor уже использует backend!

class LauncherMonitor:
    def __init__(
        self,
        config: AppConfig,
        matcher: HotkeyMatcher,
        executor: CommandExecutor,
    ) -> None:
        # ... existing code ...
        
        # TapMonitor теперь автоматически использует правильный backend!
        self.tap_monitor = TapMonitor(
            timeout=config.tap_timeout,
            verbose=config.verbose_logging,
            on_keys_detected=self._on_tap_detected,
            on_tap_invalid=None,
            check_timer_delay=self._check_timer_delay,
            # backend создаётся автоматически в TapMonitor
        )
    
    # Остальной код - БЕЗ ИЗМЕНЕНИЙ!
```

### 10. Обновление pyproject.toml

```toml
[project]
name = "tap-launcher"
version = "0.1.0"
description = "Tap Launcher: Application for detecting keyboard tap combinations"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pynput>=1.7.7",    # для X11 backend
    "typer>=0.9.0",
]

[project.optional-dependencies]
wayland = ["evdev>=1.7.0"]  # для Wayland backend

[project.scripts]
tap-detector = "tap_detector.main:app"
tap-launcher = "tap_launcher.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = [
    "src/common",          # ← ДОБАВИТЬ: общий код
    "src/tap_detector",
    "src/tap_launcher"
]
```

---

## План реализации

### Этап 1: Создание общего модуля (2-3 ч)

1. ✅ Создать структуру `src/common/`
2. ✅ Создать `common/backends/base.py`
3. ✅ Создать `common/backends/pynput_backend.py`
4. ✅ Создать `common/backends/evdev_backend.py`
5. ✅ Создать `common/backends/key_mapping.py`
6. ✅ Создать `common/backends/detector.py`
7. ✅ Переместить `key_normalizer.py` в `common/`

### Этап 2: Интеграция в tap_detector (1 ч)

1. ✅ Модифицировать `tap_detector/tap_monitor.py`
2. ✅ Обновить импорты (использовать `common.key_normalizer`)
3. ✅ Удалить старый `tap_detector/key_normalizer.py`

### Этап 3: Интеграция в tap_launcher (30 мин)

1. ✅ Обновить импорты в `tap_launcher/launcher_monitor.py`
2. ✅ Проверить, что TapMonitor автоматически использует backend

### Этап 4: Обновление конфигурации (30 мин)

1. ✅ Обновить `pyproject.toml` (добавить common в packages)
2. ✅ Обновить зависимости (добавить evdev как optional)

### Этап 5: Тестирование (2-3 ч)

1. ✅ Тестирование tap_detector на X11
2. ✅ Тестирование tap_detector на Wayland
3. ✅ Тестирование tap_launcher на X11
4. ✅ Тестирование tap_launcher на Wayland
5. ✅ Edge cases и обработка ошибок

**Общее время:** 6-8 часов работы

---

## Преимущества архитектуры

### ✅ DRY Principle
- Backend-код написан **один раз**
- Используется **обоими** приложениями
- Нет дублирования

### ✅ Минимальные изменения
- TapMonitor: добавить параметр `backend` в `__init__`
- LauncherMonitor: обновить импорт `key_normalizer`
- Вся логика остаётся нетронутой

### ✅ Модульность
- `common` - независимый модуль
- Может быть переиспользован в будущих приложениях
- Легко тестировать отдельно

### ✅ Обратная совместимость
- Backend создаётся автоматически
- Оба приложения продолжают работать на X11
- API не меняется

---

## Риски и митигация

### Риск 1: Циклические импорты

**Описание:** `tap_launcher` импортирует `TapMonitor` из `tap_detector`.

**Решение:**
- ✅ Это нормально и уже работает
- `common` не импортирует ни `tap_detector`, ни `tap_launcher`
- Зависимости однонаправленные: `tap_detector` → `common` ← `tap_launcher`

### Риск 2: Версионирование общего кода

**Описание:** Изменения в `common` влияют на оба приложения.

**Решение:**
- Тщательное тестирование изменений
- Обратная совместимость API
- Unit-тесты для `common` модуля

### Риск 3: Распространение приложений

**Описание:** Нужно убедиться, что `common` упаковывается вместе.

**Решение:**
- ✅ Добавить в `pyproject.toml`: `packages = ["src/common", ...]`
- Проверить wheel-пакет после сборки

---

## Выводы

Архитектура с общим модулем `src/common/`:
- ✅ Соответствует принципу DRY
- ✅ Минимизирует изменения в существующем коде
- ✅ Обеспечивает модульность и переиспользование
- ✅ Сохраняет обратную совместимость
- ✅ Поддерживает оба приложения одинаково

**Рекомендация:** Приступить к реализации согласно данному дизайну.

