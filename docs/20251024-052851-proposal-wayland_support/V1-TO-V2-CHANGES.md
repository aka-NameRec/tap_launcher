# Изменения от v1 к v2: Исправленная архитектура

**Дата:** 24 октября 2025

---

## Суть изменений

### ❌ V1 (неправильно)
Backend'ы размещались в `src/tap_detector/backends/` - доступны только одному приложению.

### ✅ V2 (правильно)
Backend'ы размещаются в `src/common/backends/` - **общий код для обоих приложений**.

---

## Почему v1 была неправильной?

`tap_detector` и `tap_launcher` - это **два отдельных приложения**:

1. **tap_detector** - интерактивная утилита для определения комбинаций
2. **tap_launcher** - daemon для запуска команд по тапам

**Оба** нуждаются в backend'ах для работы с клавиатурой!

В v1 backend'ы были доступны только tap_detector → нарушение DRY принципа.

---

## Сравнение архитектур

### V1: Неправильное размещение

```
src/
├── tap_detector/
│   ├── backends/              # ← Backend'ы ТУТ
│   │   ├── base.py
│   │   ├── pynput_backend.py
│   │   └── evdev_backend.py
│   ├── tap_monitor.py         # использует backends
│   └── key_normalizer.py
│
└── tap_launcher/
    ├── launcher_monitor.py    # НЕ МОЖЕТ использовать backends!
    └── ...
```

**Проблема:** tap_launcher не может использовать backend'ы из tap_detector.

### V2: Правильное размещение

```
src/
├── common/                    # ← ОБЩИЙ КОД
│   ├── backends/              # ← Backend'ы ТУТ
│   │   ├── base.py
│   │   ├── pynput_backend.py
│   │   └── evdev_backend.py
│   └── key_normalizer.py
│
├── tap_detector/
│   ├── tap_monitor.py         # использует common.backends
│   └── ...
│
└── tap_launcher/
    ├── launcher_monitor.py    # использует common.backends
    └── ...
```

**Решение:** Оба приложения используют общий код из `common`.

---

## Конкретные изменения

### 1. Структура файлов

#### V1
```
src/tap_detector/backends/      # неправильно
src/tap_detector/key_normalizer.py
```

#### V2
```
src/common/backends/            # правильно
src/common/key_normalizer.py   # переместить
```

### 2. Импорты в tap_detector/tap_monitor.py

#### V1
```python
from .backends.detector import create_backend
from .key_normalizer import normalize_key
```

#### V2
```python
from common.backends.detector import create_backend
from common.key_normalizer import normalize_key
```

### 3. Импорты в tap_launcher/launcher_monitor.py

#### V1
```python
from tap_detector.key_normalizer import format_keys_display
```

#### V2
```python
from common.key_normalizer import format_keys_display
```

### 4. pyproject.toml

#### V1
```toml
[tool.hatch.build.targets.wheel]
packages = [
    "src/tap_detector",
    "src/tap_launcher"
]
```

#### V2
```toml
[tool.hatch.build.targets.wheel]
packages = [
    "src/common",          # ← ДОБАВИТЬ
    "src/tap_detector",
    "src/tap_launcher"
]
```

---

## Зависимости модулей

### V1: Проблема с зависимостями

```
tap_launcher → tap_detector (для TapMonitor)
tap_launcher → tap_detector.key_normalizer
tap_launcher → ??? (не может использовать backends!)
```

**Проблема:** tap_launcher зависит от tap_detector слишком сильно.

### V2: Правильные зависимости

```
tap_detector → common.backends
tap_detector → common.key_normalizer
tap_launcher → common.key_normalizer
tap_launcher → tap_detector.TapMonitor (только TapMonitor!)

common → (ничего из приложений)
```

**Решение:** Общий код изолирован, зависимости однонаправленные.

---

## Миграция файлов

### Файлы для создания (новые)

```
src/common/__init__.py
src/common/backends/__init__.py
src/common/backends/base.py
src/common/backends/pynput_backend.py
src/common/backends/evdev_backend.py
src/common/backends/key_mapping.py
src/common/backends/detector.py
```

### Файлы для перемещения

```bash
git mv src/tap_detector/key_normalizer.py src/common/key_normalizer.py
```

### Файлы для изменения

```
src/tap_detector/tap_monitor.py      # обновить импорты
src/tap_launcher/launcher_monitor.py # обновить импорты
pyproject.toml                        # добавить common
```

---

## Преимущества V2

| Аспект | V1 | V2 |
|--------|----|----|
| **DRY принцип** | ❌ Нарушен | ✅ Соблюдён |
| **Модульность** | ❌ Слабая | ✅ Сильная |
| **Переиспользование** | ❌ Только tap_detector | ✅ Оба приложения |
| **Зависимости** | ❌ Запутанные | ✅ Однонаправленные |
| **Расширяемость** | ❌ Сложно | ✅ Легко |

---

## Что НЕ изменилось

Между v1 и v2 **не изменилась** сама идея backend-абстракции:

✅ Интерфейс `KeyboardBackend` - тот же  
✅ `PynputBackend` реализация - та же  
✅ `EvdevBackend` реализация - та же  
✅ Key mapping - тот же  
✅ Автоопределение backend'а - то же  

**Изменилось только РАЗМЕЩЕНИЕ кода!**

---

## Документация

### V1 документы (устарели)
- ❌ `wayland-backend-design.md` - backend'ы в tap_detector
- ❌ `WAYLAND-SUPPORT-PROPOSAL.md` - неправильная структура

### V2 документы (актуальные)
- ✅ `wayland-backend-design-v2.md` - backend'ы в common
- ✅ `WAYLAND-SUPPORT-PROPOSAL-v2.md` - правильная структура
- ✅ `PROJECT-STRUCTURE-v2.md` - визуализация структуры
- ✅ `V1-TO-V2-CHANGES.md` - этот документ

### Примеры
- `backend-examples/README-v2.md` - обновлённое описание

---

## Checklist для реализации V2

### Шаг 1: Создать структуру
- [ ] Создать `src/common/`
- [ ] Создать `src/common/backends/`
- [ ] Создать `__init__.py` файлы

### Шаг 2: Реализовать backend'ы
- [ ] `common/backends/base.py`
- [ ] `common/backends/pynput_backend.py`
- [ ] `common/backends/evdev_backend.py`
- [ ] `common/backends/key_mapping.py`
- [ ] `common/backends/detector.py`

### Шаг 3: Переместить утилиты
- [ ] `git mv tap_detector/key_normalizer.py common/key_normalizer.py`

### Шаг 4: Обновить импорты
- [ ] В `tap_detector/tap_monitor.py`
- [ ] В `tap_launcher/launcher_monitor.py`

### Шаг 5: Обновить конфигурацию
- [ ] `pyproject.toml` - добавить common в packages
- [ ] `pyproject.toml` - добавить evdev в optional-dependencies

### Шаг 6: Тестирование
- [ ] tap_detector на X11
- [ ] tap_detector на Wayland
- [ ] tap_launcher на X11
- [ ] tap_launcher на Wayland

---

## Время реализации

- **V1:** 8-12 часов (неправильная архитектура)
- **V2:** 6-8 часов (правильная архитектура)

V2 **быстрее**, потому что:
- Меньше файлов для изменения
- key_normalizer просто перемещается
- Импорты проще (common вместо tap_detector)

---

## Итог

**V2 - это исправленная версия V1** с правильным размещением общего кода.

**Ключевая идея:** Backend'ы должны быть в `src/common/`, а не в `src/tap_detector/`.

**Результат:** Оба приложения используют один и тот же код без дублирования (DRY).

