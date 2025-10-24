# Backend Implementation Examples

Эта директория содержит примеры реализации backend-абстракции для поддержки Wayland.

**ВАЖНО:** Эти файлы НЕ являются частью проекта. Они созданы для демонстрации и обсуждения технического решения.

## Файлы

### 01-base.py
Базовая абстракция `KeyboardBackend` - интерфейс, который должны реализовывать все backend'ы.

**Ключевые концепции:**
- Абстрактный класс с методами `start()`, `stop()`, `get_backend_name()`
- Callbacks для событий press/release
- Исключение `BackendNotAvailableError` для ошибок инициализации

### 02-pynput-backend.py
Реализация `PynputBackend` - обёртка над существующим pynput для X11.

**Ключевые концепции:**
- Сохраняет текущую функциональность
- Минимальная обёртка над `pynput.keyboard.Listener`
- Работает только на X11

**Можно запустить для тестирования:**
```bash
python docs/backend-examples/02-pynput-backend.py
```

### 03-evdev-backend-simplified.py
Упрощённая реализация `EvdevBackend` для Wayland.

**Ключевые концепции:**
- Читает события из `/dev/input/event*`
- Преобразует evdev key codes в pynput Key objects
- Работает и на X11, и на Wayland
- Требует прав доступа к `/dev/input/`

**Можно запустить для тестирования:**
```bash
# Установить evdev, если ещё не установлен
pip install evdev

# Запустить тест
python docs/backend-examples/03-evdev-backend-simplified.py
```

### 04-integration-example.py
Демонстрация интеграции backend'ов в `TapMonitor`.

**Ключевые концепции:**
- Показывает минимальные изменения в `TapMonitor`
- Вся логика tap detection остаётся неизменной
- Обратная совместимость через автосоздание backend'а

**Запустить для просмотра примера:**
```bash
python docs/backend-examples/04-integration-example.py
```

## Архитектура

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

## Ключевая идея

Backend'ы преобразуют события из разных источников (pynput, evdev) в **единый формат** - pynput Key/KeyCode objects.

Это означает, что:
- ✅ `TapMonitor._on_press()` не меняется
- ✅ `TapMonitor._on_release()` не меняется
- ✅ Вся логика tap detection не меняется
- ✅ `key_normalizer.py` не меняется
- ✅ Callbacks в `LauncherMonitor` не меняются

**Меняется только источник событий!**

## Сравнение изменений

### Текущий код (tap_monitor.py)

```python
def start(self):
    from pynput import keyboard
    self.listener = keyboard.Listener(
        on_press=self._on_press,
        on_release=self._on_release,
        suppress=False
    )
    self.listener.start()
    self.listener.join()
```

### С backend-абстракцией

```python
def __init__(self, ..., backend=None):
    # ...
    self.backend = backend or create_backend()

def start(self):
    self.backend.start(
        on_press=self._on_press,
        on_release=self._on_release
    )
```

**Изменения:** 2 строки в `__init__`, 1 строка в `start()`, 1 строка в `stop()`.

## Тестирование

### Proof-of-Concept тест evdev

Запусти отдельный PoC тест для проверки работы evdev в твоей системе:

```bash
# Установить evdev
pip install evdev

# Запустить тест
python docs/poc-evdev-test.py
```

Этот тест проверит:
- ✓ Доступность библиотеки evdev
- ✓ Права доступа к `/dev/input/`
- ✓ Поиск клавиатурных устройств
- ✓ Чтение событий клавиатуры
- ✓ Определение тапов

## Следующие шаги

1. Изучить технический дизайн: `docs/wayland-backend-design.md`
2. Запустить PoC тесты для проверки evdev
3. Обсудить архитектурное решение
4. Реализовать backend-абстракцию в проекте
5. Протестировать на X11 и Wayland

## Вопросы для обсуждения

- Устраивает ли архитектура backend-абстракции?
- Есть ли замечания по API backend'ов?
- Правильно ли выбран подход к маппингу ключей?
- Нужны ли дополнительные конфигурационные опции?

