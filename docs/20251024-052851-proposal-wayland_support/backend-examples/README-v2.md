# Backend Implementation Examples (v2 - исправлено)

**Версия:** 2.0 (с учётом общего модуля `common`)

Эта директория содержит примеры реализации backend-абстракции для поддержки Wayland.

**ВАЖНО:** Эти файлы НЕ являются частью проекта. Они созданы для демонстрации и обсуждения технического решения.

---

## Изменения от v1

### ❌ v1 (неправильно):
Backend'ы предлагались в `src/tap_detector/backends/` - только для одного приложения.

### ✅ v2 (правильно):
Backend'ы должны быть в `src/common/backends/` - **общий код для обоих приложений**.

---

## Структура v2

В реальном проекте backend'ы будут размещены так:

```
src/
├── common/                      # ← ОБЩИЙ модуль
│   ├── backends/                # ← Backend'ы здесь!
│   │   ├── base.py
│   │   ├── pynput_backend.py
│   │   ├── evdev_backend.py
│   │   ├── key_mapping.py
│   │   └── detector.py
│   └── key_normalizer.py
│
├── tap_detector/                # использует common.backends
│   └── tap_monitor.py
│
└── tap_launcher/                # использует common.backends
    └── launcher_monitor.py
```

---

## Примеры в этом каталоге

### 01-base.py
Базовая абстракция `KeyboardBackend`.

**Что показывает:**
- Интерфейс, который реализуют все backend'ы
- Методы `start()`, `stop()`, `get_backend_name()`
- Исключение `BackendNotAvailableError`

**В реальном проекте:** `src/common/backends/base.py`

### 02-pynput-backend.py
Реализация `PynputBackend` для X11.

**Что показывает:**
- Обёртка над `pynput.keyboard.Listener`
- Сохранение текущей функциональности
- Работает только на X11

**В реальном проекте:** `src/common/backends/pynput_backend.py`

**Можно запустить:**
```bash
python docs/backend-examples/02-pynput-backend.py
```

### 03-evdev-backend-simplified.py
Упрощённая реализация `EvdevBackend` для Wayland.

**Что показывает:**
- Чтение событий из `/dev/input/event*`
- Преобразование evdev key codes → pynput Keys
- Работает на X11 и Wayland

**В реальном проекте:** `src/common/backends/evdev_backend.py`

**Можно запустить:**
```bash
pip install evdev
python docs/backend-examples/03-evdev-backend-simplified.py
```

### 04-integration-example.py
Демонстрация интеграции в `TapMonitor`.

**Что показывает:**
- Минимальные изменения в TapMonitor
- Backend создаётся автоматически
- Вся логика tap detection не меняется

**Запустить для просмотра:**
```bash
python docs/backend-examples/04-integration-example.py
```

---

## Ключевые изменения для v2

### Импорты

#### В примерах v1 (неправильно):
```python
# Было бы в tap_detector/tap_monitor.py
from .backends.detector import create_backend
```

#### В v2 (правильно):
```python
# Должно быть в tap_detector/tap_monitor.py
from common.backends.detector import create_backend

# И в tap_launcher/launcher_monitor.py
from common.backends.detector import create_backend
from common.key_normalizer import format_keys_display
```

### Использование в обоих приложениях

```python
# tap_detector/tap_monitor.py
from common.backends.detector import create_backend

class TapMonitor:
    def __init__(self, ..., backend=None):
        self.backend = backend or create_backend()

# tap_launcher/launcher_monitor.py
from common.key_normalizer import format_keys_display
from tap_detector.tap_monitor import TapMonitor

class LauncherMonitor:
    def __init__(self, ...):
        # TapMonitor уже использует backend из common!
        self.tap_monitor = TapMonitor(...)
```

---

## Архитектура

```
┌─────────────────┐         ┌─────────────────┐
│  tap_detector   │         │  tap_launcher   │
│   (app 1)       │         │   (app 2)       │
└────────┬────────┘         └────────┬────────┘
         │                           │
         │ import                    │ import
         │                           │
         └────────────┬──────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │    src/common/         │
         │                        │
         │  ┌──────────────────┐ │
         │  │   backends/      │ │
         │  │                  │ │
         │  │ • base           │ │
         │  │ • pynput_backend │ │
         │  │ • evdev_backend  │ │
         │  │ • detector       │ │
         │  └──────────────────┘ │
         │                        │
         │  • key_normalizer      │
         └────────────────────────┘
```

---

## Как использовать примеры

### Шаг 1: Понять концепцию

Прочитать файлы в порядке:
1. `01-base.py` - базовая абстракция
2. `02-pynput-backend.py` - X11 реализация
3. `03-evdev-backend-simplified.py` - Wayland реализация
4. `04-integration-example.py` - интеграция

### Шаг 2: Запустить примеры

```bash
# X11 backend (работает сейчас)
python 02-pynput-backend.py

# Wayland backend (требует evdev)
pip install evdev
python 03-evdev-backend-simplified.py

# Интеграция (демонстрация)
python 04-integration-example.py
```

### Шаг 3: Изучить полный дизайн

Прочитать документацию:
- `../PROJECT-STRUCTURE-v2.md` - структура проекта
- `../wayland-backend-design-v2.md` - детальный дизайн
- `../WAYLAND-SUPPORT-PROPOSAL-v2.md` - предложение

---

## Отличия от реального кода

Примеры упрощены для демонстрации:

1. **Логирование:** В примерах минимально, в реальном коде - полное
2. **Обработка ошибок:** В примерах упрощена
3. **Key mapping:** В примерах неполный, в реальном - все ключи
4. **Device detection:** В примерах базовый, в реальном - продвинутый

---

## Что делать дальше

### Для изучения:
1. ✅ Прочитать примеры
2. ✅ Запустить тесты
3. ✅ Изучить полный дизайн

### Для реализации:
1. ⏸️ Создать `src/common/backends/`
2. ⏸️ Реализовать все backend'ы
3. ⏸️ Переместить `key_normalizer.py` в `common/`
4. ⏸️ Обновить импорты в обоих приложениях
5. ⏸️ Протестировать на X11 и Wayland

---

## Вопросы?

- **Структура:** Смотри `../PROJECT-STRUCTURE-v2.md`
- **Дизайн:** Смотри `../wayland-backend-design-v2.md`
- **Предложение:** Смотри `../WAYLAND-SUPPORT-PROPOSAL-v2.md`
- **PoC тест:** Запусти `../poc-evdev-test.py`

