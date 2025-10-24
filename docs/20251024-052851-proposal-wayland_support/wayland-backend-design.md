# Технический дизайн: Backend-абстракция для поддержки Wayland

**Дата:** 24 октября 2025  
**Версия:** 1.0  
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

**tap_launcher** и **tap_detector** используют библиотеку `pynput` для перехвата событий клавиатуры:

```python
# tap_detector/tap_monitor.py
from pynput import keyboard

self.listener = keyboard.Listener(
    on_press=self._on_press,
    on_release=self._on_release,
    suppress=False
)
```

**Проблема:** `pynput` работает только с X11 и не поддерживает Wayland.

### Почему это критично?

- KUbuntu 25.10 использует Wayland по умолчанию
- Переход на Wayland неизбежен для современных Linux-дистрибутивов
- Текущий код полностью неработоспособен в Wayland-сессиях

---

## Цели и ограничения

### Цели

1. ✅ **Добавить поддержку Wayland** без потери функциональности
2. ✅ **Сохранить работу X11** (обратная совместимость)
3. ✅ **Минимизировать изменения** в существующем коде
4. ✅ **Прозрачное переключение** между backend'ами (автоопределение)
5. ✅ **Единая кодовая база** для X11 и Wayland

### Ограничения

1. ⚠️ Wayland требует прав доступа к `/dev/input/*` (группа `input`)
2. ⚠️ evdev работает на более низком уровне (key codes vs Key objects)
3. ⚠️ Не все клавиши могут иметь прямой маппинг
4. ⚠️ Необходимо поддерживать два разных API

---

## Архитектурное решение

### Ключевая идея: Backend-абстракция

Создать **абстрактный слой** между источником событий клавиатуры и логикой tap detection:

```
┌─────────────────────────────────────────┐
│         TapMonitor (логика)            │
│  (определение тапов, таймауты, etc)    │
└─────────────────┬───────────────────────┘
                  │
                  │ callbacks: on_press, on_release
                  │
┌─────────────────▼───────────────────────┐
│      KeyboardBackend (абстракция)      │
│   start(), stop(), event callbacks     │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼──────┐    ┌───────▼──────┐
│  PynputBackend│    │ EvdevBackend │
│     (X11)     │    │  (Wayland)   │
└───────────────┘    └──────────────┘
```

### Преимущества

- ✅ **Изоляция:** Логика tap detection не зависит от источника событий
- ✅ **Расширяемость:** Легко добавить другие backend'ы (Windows, macOS)
- ✅ **Тестируемость:** Backend можно замокать для unit-тестов
- ✅ **Гибкость:** Можно явно выбрать backend или использовать автоопределение

---

## Детальный дизайн

### 1. Структура файлов

```
src/tap_detector/
├── __init__.py
├── main.py
├── tap_monitor.py               # изменения: использует backend
├── formatter.py
├── key_normalizer.py
├── constants.py
├── backends/                    # ← НОВЫЙ каталог
│   ├── __init__.py
│   ├── base.py                  # ← базовая абстракция
│   ├── pynput_backend.py        # ← X11 реализация
│   ├── evdev_backend.py         # ← Wayland реализация
│   ├── key_mapping.py           # ← evdev → pynput маппинг
│   └── detector.py              # ← автоопределение backend
```

### 2. Базовая абстракция

**`backends/base.py`:**

```python
"""Base keyboard backend abstraction."""

from abc import ABC, abstractmethod
from typing import Any, Callable


class KeyboardBackend(ABC):
    """Abstract interface for keyboard event sources.
    
    A backend is responsible for:
    - Listening to keyboard events from the system
    - Converting events to a unified format
    - Calling callbacks for press/release events
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
            on_release: Callback for key release events
        
        Note:
            This method should block until stop() is called.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop listening for keyboard events.
        
        This method should cause start() to unblock and return.
        """
        pass
    
    @abstractmethod
    def get_backend_name(self) -> str:
        """Return the name of this backend (for logging/debugging)."""
        pass


class BackendNotAvailableError(Exception):
    """Raised when a backend cannot be initialized."""
    pass
```

### 3. PynputBackend (X11)

**`backends/pynput_backend.py`:**

```python
"""Pynput-based keyboard backend for X11."""

import logging
from typing import Any, Callable

from .base import BackendNotAvailableError, KeyboardBackend


class PynputBackend(KeyboardBackend):
    """Keyboard backend using pynput (X11 only).
    
    This backend uses the pynput library which works well on X11
    but is not compatible with Wayland.
    """
    
    def __init__(self) -> None:
        """Initialize pynput backend."""
        self.logger = logging.getLogger('tap_detector.backend.pynput')
        self.listener: Any = None  # pynput.keyboard.Listener
        
        # Check if pynput is available
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
        """Start listening using pynput.
        
        Args:
            on_press: Callback for key press (receives pynput Key/KeyCode)
            on_release: Callback for key release (receives pynput Key/KeyCode)
        """
        from pynput import keyboard
        
        self.logger.info('Starting pynput keyboard listener (X11)')
        
        self.listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
            suppress=False  # Don't suppress events for other apps
        )
        
        self.listener.start()
        self.listener.join()  # Block until stopped
    
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

### 4. EvdevBackend (Wayland)

**`backends/evdev_backend.py`:**

```python
"""Evdev-based keyboard backend for Wayland."""

import logging
import threading
from typing import Any, Callable

from .base import BackendNotAvailableError, KeyboardBackend
from .key_mapping import evdev_to_pynput_key


class EvdevBackend(KeyboardBackend):
    """Keyboard backend using evdev (works with both X11 and Wayland).
    
    This backend reads events directly from /dev/input/event* devices,
    which requires the user to be in the 'input' group or run with
    elevated privileges.
    """
    
    def __init__(self, device_path: str | None = None) -> None:
        """Initialize evdev backend.
        
        Args:
            device_path: Optional path to specific input device.
                        If None, will auto-detect keyboard device.
        
        Raises:
            BackendNotAvailableError: If evdev is not available or
                                     no keyboard device found.
        """
        self.logger = logging.getLogger('tap_detector.backend.evdev')
        self.device_path = device_path
        self.device: Any = None  # evdev.InputDevice
        self._stop_event = threading.Event()
        
        # Check if evdev is available
        try:
            import evdev  # noqa: F401
        except ImportError as e:
            raise BackendNotAvailableError(
                'evdev library is not installed. '
                'Install it with: pip install evdev'
            ) from e
        
        self.logger.debug('EvdevBackend initialized')
    
    def _find_keyboard_device(self) -> Any:
        """Find a keyboard device in /dev/input/.
        
        Returns:
            evdev.InputDevice: The keyboard device
        
        Raises:
            BackendNotAvailableError: If no keyboard found or access denied
        """
        import evdev
        from evdev import ecodes
        
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        except PermissionError as e:
            raise BackendNotAvailableError(
                'Permission denied accessing /dev/input/. '
                'Add user to "input" group: sudo usermod -a -G input $USER'
            ) from e
        
        # Find devices with keyboard capabilities
        keyboards = []
        for device in devices:
            caps = device.capabilities()
            # Check if device has EV_KEY events and common keyboard keys
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                # Check for common modifier keys to identify keyboards
                if (ecodes.KEY_LEFTCTRL in keys or 
                    ecodes.KEY_RIGHTCTRL in keys or
                    ecodes.KEY_LEFTALT in keys):
                    keyboards.append(device)
                    self.logger.debug(
                        f'Found keyboard: {device.name} at {device.path}'
                    )
        
        if not keyboards:
            raise BackendNotAvailableError('No keyboard device found')
        
        # Use the first keyboard found (or specified device)
        selected = keyboards[0]
        self.logger.info(f'Using keyboard device: {selected.name}')
        return selected
    
    def start(
        self,
        on_press: Callable[[Any], None],
        on_release: Callable[[Any], None]
    ) -> None:
        """Start listening using evdev.
        
        Args:
            on_press: Callback for key press (receives pynput-compatible Key)
            on_release: Callback for key release (receives pynput-compatible Key)
        """
        from evdev import categorize, ecodes
        
        # Find or open device
        if self.device_path:
            import evdev
            self.device = evdev.InputDevice(self.device_path)
            self.logger.info(f'Using specified device: {self.device_path}')
        else:
            self.device = self._find_keyboard_device()
        
        self.logger.info('Starting evdev keyboard listener (Wayland)')
        self._stop_event.clear()
        
        # Grab device for exclusive access (optional - commented out by default)
        # self.device.grab()
        
        try:
            # Read events in a loop
            for event in self.device.read_loop():
                # Check if we should stop
                if self._stop_event.is_set():
                    break
                
                # Process keyboard events only
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    keycode = key_event.keycode
                    
                    # Convert evdev keycode to pynput Key object
                    try:
                        pynput_key = evdev_to_pynput_key(keycode)
                    except KeyError:
                        # Unknown key, skip
                        self.logger.debug(f'Unknown keycode: {keycode}')
                        continue
                    
                    # Call appropriate callback
                    if key_event.keystate == key_event.key_down:
                        on_press(pynput_key)
                    elif key_event.keystate == key_event.key_up:
                        on_release(pynput_key)
                    # key_hold (keystate=2) is ignored
        
        finally:
            # Ungrab device
            # self.device.ungrab()
            pass
    
    def stop(self) -> None:
        """Stop the evdev listener."""
        self.logger.info('Stopping evdev keyboard listener')
        self._stop_event.set()
        
        # Close device
        if self.device:
            self.device.close()
            self.device = None
    
    def get_backend_name(self) -> str:
        """Return backend name."""
        return 'evdev (Wayland/X11)'
```

### 5. Key Mapping

**`backends/key_mapping.py`:**

```python
"""Mapping between evdev key codes and pynput Key objects."""

from typing import Any


# Import pynput Key class for mapping
try:
    from pynput.keyboard import Key, KeyCode
except ImportError:
    # If pynput not available, create dummy classes
    class Key:  # type: ignore
        pass
    class KeyCode:  # type: ignore
        pass


# Mapping from evdev key codes to pynput Key objects
# Based on: /usr/include/linux/input-event-codes.h
EVDEV_TO_PYNPUT_KEY: dict[str, Any] = {
    # Modifiers - Left side
    'KEY_LEFTCTRL': Key.ctrl_l,
    'KEY_LEFTSHIFT': Key.shift_l,
    'KEY_LEFTALT': Key.alt_l,
    'KEY_LEFTMETA': Key.cmd_l,  # Super/Win key
    
    # Modifiers - Right side
    'KEY_RIGHTCTRL': Key.ctrl_r,
    'KEY_RIGHTSHIFT': Key.shift_r,
    'KEY_RIGHTALT': Key.alt_r,
    'KEY_RIGHTMETA': Key.cmd_r,
    
    # Special keys
    'KEY_ESC': Key.esc,
    'KEY_ENTER': Key.enter,
    'KEY_TAB': Key.tab,
    'KEY_BACKSPACE': Key.backspace,
    'KEY_DELETE': Key.delete,
    'KEY_INSERT': Key.insert,
    'KEY_SPACE': Key.space,
    
    # Navigation
    'KEY_HOME': Key.home,
    'KEY_END': Key.end,
    'KEY_PAGEUP': Key.page_up,
    'KEY_PAGEDOWN': Key.page_down,
    'KEY_UP': Key.up,
    'KEY_DOWN': Key.down,
    'KEY_LEFT': Key.left,
    'KEY_RIGHT': Key.right,
    
    # Function keys
    'KEY_F1': Key.f1,
    'KEY_F2': Key.f2,
    'KEY_F3': Key.f3,
    'KEY_F4': Key.f4,
    'KEY_F5': Key.f5,
    'KEY_F6': Key.f6,
    'KEY_F7': Key.f7,
    'KEY_F8': Key.f8,
    'KEY_F9': Key.f9,
    'KEY_F10': Key.f10,
    'KEY_F11': Key.f11,
    'KEY_F12': Key.f12,
    
    # Lock keys
    'KEY_CAPSLOCK': Key.caps_lock,
    'KEY_NUMLOCK': Key.num_lock,
    'KEY_SCROLLLOCK': Key.scroll_lock,
    
    # Media keys
    'KEY_MUTE': Key.media_volume_mute,
    'KEY_VOLUMEDOWN': Key.media_volume_down,
    'KEY_VOLUMEUP': Key.media_volume_up,
    'KEY_PLAYPAUSE': Key.media_play_pause,
    'KEY_STOPCD': Key.media_stop,
    'KEY_PREVIOUSSONG': Key.media_previous,
    'KEY_NEXTSONG': Key.media_next,
    
    # Printscreen/Pause
    'KEY_PRINT': Key.print_screen,
    'KEY_PAUSE': Key.pause,
    
    # Menu key
    'KEY_MENU': Key.menu,
}

# Alphanumeric keys are handled separately as KeyCode objects
# A-Z: KEY_A ... KEY_Z
# 0-9: KEY_0 ... KEY_9


def evdev_to_pynput_key(keycode: str | list[str]) -> Any:
    """Convert evdev keycode to pynput Key/KeyCode object.
    
    Args:
        keycode: Evdev keycode string (e.g., 'KEY_LEFTCTRL')
                or list of keycodes for multi-key events
    
    Returns:
        pynput Key or KeyCode object
    
    Raises:
        KeyError: If keycode is not recognized
    """
    # Handle multi-key events (take first one)
    if isinstance(keycode, list):
        keycode = keycode[0]
    
    # Check if it's a special key (modifier, function, etc.)
    if keycode in EVDEV_TO_PYNPUT_KEY:
        return EVDEV_TO_PYNPUT_KEY[keycode]
    
    # Handle alphanumeric keys
    # KEY_A ... KEY_Z
    if keycode.startswith('KEY_') and len(keycode) == 5:
        char = keycode[4].lower()
        if char.isalpha():
            return KeyCode.from_char(char)
    
    # KEY_0 ... KEY_9
    if keycode.startswith('KEY_') and keycode[4:].isdigit():
        char = keycode[4]
        return KeyCode.from_char(char)
    
    # Unknown keycode
    raise KeyError(f'Unknown evdev keycode: {keycode}')
```

### 6. Backend Auto-detection

**`backends/detector.py`:**

```python
"""Backend detection and factory."""

import logging
import os
from typing import Any

from .base import BackendNotAvailableError, KeyboardBackend
from .evdev_backend import EvdevBackend
from .pynput_backend import PynputBackend


logger = logging.getLogger('tap_detector.backend')


def detect_session_type() -> str:
    """Detect current display server type.
    
    Returns:
        str: 'wayland', 'x11', or 'unknown'
    """
    session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
    
    if session_type:
        logger.debug(f'Detected session type from XDG_SESSION_TYPE: {session_type}')
        return session_type
    
    # Fallback: check for WAYLAND_DISPLAY or DISPLAY
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
                     If None or 'auto', will auto-detect based on session type
        **kwargs: Additional arguments passed to backend constructor
    
    Returns:
        KeyboardBackend: Initialized backend instance
    
    Raises:
        BackendNotAvailableError: If no suitable backend available
    """
    # Auto-detect if not specified
    if backend_name is None or backend_name == 'auto':
        session_type = detect_session_type()
        
        if session_type == 'wayland':
            backend_name = 'evdev'
        elif session_type == 'x11':
            backend_name = 'pynput'
        else:
            # Unknown session - try pynput first, then evdev
            logger.warning('Unknown session type, trying pynput first')
            backend_name = 'pynput'
    
    # Try to create the specified backend
    if backend_name == 'pynput':
        try:
            backend = PynputBackend(**kwargs)
            logger.info(f'Using backend: {backend.get_backend_name()}')
            return backend
        except BackendNotAvailableError as e:
            # If explicitly requested and failed, try fallback
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

### 7. Интеграция в TapMonitor

**Изменения в `tap_monitor.py`:**

```python
# Добавить в imports:
from .backends.detector import create_backend
from .backends.base import KeyboardBackend

class TapMonitor:
    def __init__(
        self,
        timeout: float | None = None,
        verbose: bool = False,
        on_keys_detected: Callable[[set[Any], float], None] | None = None,
        on_tap_invalid: Callable[[str, set[Any], float], None] | None = None,
        check_timer_delay: Callable[[str], bool] | None = None,
        backend: KeyboardBackend | None = None,  # ← НОВЫЙ параметр
    ) -> None:
        self.timeout = timeout
        self.validate_timeout = timeout is not None
        self.verbose = verbose
        self.state = TapState()
        self.on_keys_detected = on_keys_detected
        self.on_tap_invalid = on_tap_invalid
        self.check_timer_delay = check_timer_delay
        
        # Create or use provided backend
        self.backend = backend or create_backend()  # ← НОВОЕ
        self.listener: Any = None  # Deprecated, kept for compatibility
    
    def start(self) -> None:
        """Start monitoring keyboard events (blocking)."""
        # Use backend instead of creating pynput Listener directly
        self.backend.start(
            on_press=self._on_press,
            on_release=self._on_release
        )
    
    def stop(self) -> None:
        """Stop monitoring keyboard events."""
        self.backend.stop()
```

---

## План реализации

### Этап 1: Создание backend-абстракции (2-3 часа)

1. ✅ Создать каталог `src/tap_detector/backends/`
2. ✅ Реализовать `base.py` (абстракция)
3. ✅ Реализовать `pynput_backend.py` (текущая функциональность)
4. ✅ Реализовать `key_mapping.py` (маппинг ключей)
5. ✅ Реализовать `detector.py` (автоопределение)

### Этап 2: Реализация evdev backend (3-4 часа)

1. ✅ Реализовать `evdev_backend.py`
2. ✅ Добавить поиск устройства клавиатуры
3. ✅ Реализовать обработку событий
4. ✅ Протестировать маппинг всех клавиш

### Этап 3: Интеграция (1-2 часа)

1. ✅ Модифицировать `TapMonitor.__init__` для приёма backend
2. ✅ Модифицировать `TapMonitor.start()` для использования backend
3. ✅ Модифицировать `TapMonitor.stop()`
4. ✅ Обновить `LauncherMonitor` (без изменений, если API совместимо)

### Этап 4: Зависимости и конфигурация (30 мин)

1. ✅ Обновить `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   wayland = ["evdev>=1.7.0"]
   ```
2. ✅ Добавить инструкции по установке в README

### Этап 5: Документация и тестирование (2-3 часа)

1. ✅ Документировать настройку прав для evdev
2. ✅ Создать примеры использования
3. ✅ Тестирование в X11
4. ✅ Тестирование в Wayland
5. ✅ Обработка ошибок и edge cases

**Общее время:** 8-12 часов

---

## Риски и митигация

### Риск 1: Права доступа к /dev/input

**Описание:** evdev требует доступа к `/dev/input/event*`.

**Митигация:**
- Документировать необходимость добавления в группу `input`
- Предоставить понятное сообщение об ошибке с инструкциями
- Автоматическая проверка прав при запуске

### Риск 2: Неполный маппинг клавиш

**Описание:** Некоторые evdev key codes могут не иметь эквивалента в pynput.

**Митигация:**
- Логировать неизвестные ключи для постепенного расширения маппинга
- Graceful handling неизвестных ключей (пропуск)
- Открыть issue tracking для дополнения маппинга

### Риск 3: Производительность evdev

**Описание:** Чтение из `/dev/input` может быть медленнее.

**Митигация:**
- Профилирование производительности
- Оптимизация event loop при необходимости
- В текущей задаче (tap detection) производительность не критична

### Риск 4: Multiple keyboard devices

**Описание:** Система может иметь несколько клавиатурных устройств.

**Митигация:**
- Автоопределение выбирает первое найденное
- Возможность явно указать device path через конфиг
- Логирование всех найденных устройств

### Риск 5: Grab vs non-grab режим

**Описание:** `device.grab()` дает эксклюзивный доступ, но блокирует другие приложения.

**Митигация:**
- По умолчанию НЕ использовать grab (как в pynput)
- Опция в конфиге для включения grab при необходимости
- Документировать разницу

---

## Альтернативные решения (рассмотрены и отклонены)

### Альтернатива 1: Полная замена pynput на evdev

**Плюсы:** Единый backend для всех платформ  
**Минусы:**
- Потеря кроссплатформенности (Windows/macOS)
- Требует больших изменений
- evdev более низкоуровневый, сложнее в использовании

**Вердикт:** ❌ Отклонено

### Альтернатива 2: Использование libinput

**Плюсы:** "Правильный" способ для Wayland  
**Минусы:**
- Python bindings незрелые
- Сложнее в использовании
- Те же требования к правам

**Вердикт:** ❌ Отклонено (evdev проще и достаточно)

### Альтернатива 3: Compositor-specific (KWin scripts)

**Плюсы:** Не требует особых прав  
**Минусы:**
- Работает только в KDE
- Ограниченный API
- Не переносимо

**Вердикт:** ❌ Отклонено (не универсально)

---

## Выводы

Backend-абстракция - **оптимальное решение** для поддержки Wayland:

✅ Минимальные изменения в существующем коде  
✅ Обратная совместимость с X11  
✅ Чистая архитектура  
✅ Расширяемость  
✅ Приемлемая сложность реализации  

**Рекомендация:** Приступить к реализации согласно данному дизайну.

