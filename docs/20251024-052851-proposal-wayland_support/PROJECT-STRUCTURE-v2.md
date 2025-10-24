# Структура проекта с общим модулем (v2)

**Дата:** 24 октября 2025  
**Версия:** 2.0

---

## Текущая структура (до изменений)

```
/home/shtirliz/workspace/myself/tap_launcher/
├── src/
│   ├── tap_detector/              # Приложение 1
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── tap_monitor.py         # ← использует pynput напрямую
│   │   ├── formatter.py
│   │   ├── key_normalizer.py      # ← утилиты нормализации ключей
│   │   └── constants.py
│   │
│   └── tap_launcher/              # Приложение 2
│       ├── __init__.py
│       ├── main.py
│       ├── launcher_monitor.py    # ← использует TapMonitor
│       ├── hotkey_matcher.py
│       ├── command_executor.py
│       ├── config_loader.py
│       ├── daemon_manager.py
│       └── models.py
│
├── pyproject.toml
├── config/
│   └── tap-launcher.toml.example
├── docs/
└── README.md
```

**Проблемы:**
- ❌ pynput используется напрямую (только X11)
- ❌ key_normalizer в tap_detector, но используется в tap_launcher
- ❌ Нет общего кода - дублирование потенциально возможно

---

## Предлагаемая структура (после изменений)

```
/home/shtirliz/workspace/myself/tap_launcher/
├── src/
│   ├── common/                    # ← НОВЫЙ: общий модуль
│   │   ├── __init__.py
│   │   │
│   │   ├── backends/              # ← Backend'ы клавиатуры
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Абстракция KeyboardBackend
│   │   │   ├── pynput_backend.py # X11 реализация
│   │   │   ├── evdev_backend.py  # Wayland реализация
│   │   │   ├── key_mapping.py    # evdev→pynput маппинг
│   │   │   └── detector.py       # Автоопределение backend'а
│   │   │
│   │   └── key_normalizer.py     # ← ПЕРЕМЕСТИТЬ из tap_detector
│   │       # normalize_key(), format_keys_display()
│   │
│   ├── tap_detector/              # Приложение 1
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── tap_monitor.py         # ← ИЗМЕНИТЬ: использует common.backends
│   │   ├── formatter.py
│   │   └── constants.py
│   │
│   └── tap_launcher/              # Приложение 2
│       ├── __init__.py
│       ├── main.py
│       ├── launcher_monitor.py    # ← ИЗМЕНИТЬ: импорт из common
│       ├── hotkey_matcher.py
│       ├── command_executor.py
│       ├── config_loader.py
│       ├── daemon_manager.py
│       └── models.py
│
├── pyproject.toml                 # ← ИЗМЕНИТЬ: добавить common
├── config/
│   └── tap-launcher.toml.example
├── docs/
│   ├── wayland-backend-design-v2.md
│   ├── WAYLAND-SUPPORT-PROPOSAL-v2.md
│   └── PROJECT-STRUCTURE-v2.md    # ← этот файл
└── README.md
```

**Преимущества:**
- ✅ Backend-код в одном месте (DRY)
- ✅ Используется обоими приложениями
- ✅ Поддержка X11 и Wayland
- ✅ Модульная архитектура

---

## Диаграмма зависимостей

```
┌─────────────────────────────────────────────────────┐
│                   tap_detector                      │
│                  (приложение 1)                     │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │           TapMonitor                         │  │
│  │  (отображает нажатые клавиши)                │  │
│  │                                              │  │
│  │  import common.backends.detector             │  │
│  │  import common.key_normalizer                │  │
│  └──────────────────┬───────────────────────────┘  │
└────────────────────┼────────────────────────────────┘
                     │
                     │ использует
                     │
┌────────────────────▼─────────────────────────────────┐
│                  src/common/                         │
│                (ОБЩИЙ МОДУЛЬ)                        │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │           backends/                            │ │
│  │                                                │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │  KeyboardBackend (абстракция)            │ │ │
│  │  └──────────────┬──────────────┬────────────┘ │ │
│  │                 │              │              │ │
│  │     ┌───────────▼────┐   ┌────▼──────────┐   │ │
│  │     │ PynputBackend  │   │ EvdevBackend  │   │ │
│  │     │    (X11)       │   │  (Wayland)    │   │ │
│  │     └────────────────┘   └───────────────┘   │ │
│  │                                                │ │
│  │  key_mapping.py (evdev→pynput)                │ │
│  │  detector.py (автоопределение)                │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  key_normalizer.py (нормализация ключей)            │
└────────────────────┬─────────────────────────────────┘
                     │
                     │ использует
                     │
┌────────────────────▼─────────────────────────────────┐
│                  tap_launcher                        │
│                 (приложение 2)                       │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │         LauncherMonitor                        │ │
│  │  (запускает команды по тапам)                  │ │
│  │                                                │ │
│  │  import common.key_normalizer                  │ │
│  │  создаёт TapMonitor (который уже использует    │ │
│  │  common.backends автоматически)                │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## Зависимости импортов

### Модуль `common`

**Не импортирует:**
- ❌ tap_detector
- ❌ tap_launcher

**Импортирует:**
- ✅ pynput (стандартная библиотека)
- ✅ evdev (опциональная библиотека)
- ✅ стандартные модули Python

### Модуль `tap_detector`

**Импортирует:**
- ✅ `common.backends.detector`
- ✅ `common.backends.base`
- ✅ `common.key_normalizer`

**Не импортирует:**
- ❌ tap_launcher

### Модуль `tap_launcher`

**Импортирует:**
- ✅ `tap_detector.tap_monitor` (уже так)
- ✅ `common.key_normalizer` (вместо tap_detector.key_normalizer)

**Итог:** Зависимости однонаправленные, циклов нет. ✅

---

## Изменения в файлах

### Файлы для создания

```
src/common/__init__.py                    # пустой
src/common/backends/__init__.py           # экспорт классов
src/common/backends/base.py              # ~50 строк
src/common/backends/pynput_backend.py    # ~60 строк
src/common/backends/evdev_backend.py     # ~150 строк
src/common/backends/key_mapping.py       # ~100 строк
src/common/backends/detector.py          # ~80 строк
```

### Файлы для перемещения

```
src/tap_detector/key_normalizer.py
  → src/common/key_normalizer.py
```

### Файлы для изменения

```
src/tap_detector/tap_monitor.py
  - изменить импорты (использовать common.key_normalizer)
  - добавить параметр backend в __init__
  - использовать backend.start() вместо pynput напрямую

src/tap_launcher/launcher_monitor.py
  - изменить импорт key_normalizer (из common)

pyproject.toml
  - добавить src/common в packages
  - добавить evdev в optional-dependencies
```

---

## Примеры использования

### В tap_detector/tap_monitor.py

```python
# До изменений:
from pynput import keyboard
from .key_normalizer import normalize_key

class TapMonitor:
    def start(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        self.listener.join()

# После изменений:
from common.key_normalizer import normalize_key
from common.backends.detector import create_backend
from common.backends.base import KeyboardBackend

class TapMonitor:
    def __init__(self, ..., backend: KeyboardBackend | None = None):
        # ...
        self.backend = backend or create_backend()
    
    def start(self):
        self.backend.start(
            on_press=self._on_press,
            on_release=self._on_release
        )
```

### В tap_launcher/launcher_monitor.py

```python
# До изменений:
from tap_detector.key_normalizer import format_keys_display

# После изменений:
from common.key_normalizer import format_keys_display

# TapMonitor уже использует backend - никаких других изменений!
```

---

## Миграционный план

### Шаг 1: Создать структуру common

```bash
mkdir -p src/common/backends
touch src/common/__init__.py
touch src/common/backends/__init__.py
```

### Шаг 2: Создать backend файлы

```bash
# Создать все backend файлы согласно дизайну
```

### Шаг 3: Переместить key_normalizer

```bash
git mv src/tap_detector/key_normalizer.py src/common/key_normalizer.py
```

### Шаг 4: Обновить импорты

```bash
# Заменить импорты в tap_detector и tap_launcher
```

### Шаг 5: Обновить pyproject.toml

```bash
# Добавить common в packages
```

### Шаг 6: Тестирование

```bash
# Запустить оба приложения на X11 и Wayland
```

---

## Тестирование структуры

### Проверка импортов

```python
# Проверить, что импорты работают:
from common.backends.detector import create_backend
from common.key_normalizer import normalize_key
from tap_detector.tap_monitor import TapMonitor
from tap_launcher.launcher_monitor import LauncherMonitor
```

### Проверка упаковки

```bash
# Собрать wheel и проверить содержимое
uv build
unzip -l dist/*.whl | grep -E '(common|tap_detector|tap_launcher)'
```

---

## Итоговая структура (краткая)

```
src/
├── common/              # Общий код для обоих приложений
│   ├── backends/        # Backend'ы клавиатуры (X11, Wayland)
│   └── key_normalizer   # Утилиты работы с клавишами
│
├── tap_detector/        # Приложение 1: интерактивный детектор
└── tap_launcher/        # Приложение 2: daemon-launcher
```

**Принцип:** Общий код выделен, каждое приложение использует его независимо.

---

## Вопросы и ответы

### Q: Почему не backend в tap_detector?
**A:** Потому что tap_launcher тоже использует backend'ы. DRY принцип.

### Q: Что ещё можно вынести в common?
**A:** Пока только backends и key_normalizer. Остальное специфично для приложений.

### Q: Как обновлять common без breaking changes?
**A:** Тщательно тестировать оба приложения, сохранять обратную совместимость API.

### Q: Можно ли добавить third-party backend?
**A:** Да! Нужно только реализовать KeyboardBackend интерфейс.

---

## Ссылки

- **Технический дизайн v2:** `docs/wayland-backend-design-v2.md`
- **Предложение v2:** `docs/WAYLAND-SUPPORT-PROPOSAL-v2.md`
- **ConPort решение:** ID 9

