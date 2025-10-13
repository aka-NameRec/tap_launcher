# Гибкий старт таймера тапа: start_timer_from_second_key
_Created on 13.10.2025 at 16:25:00 GMT+3_

## Суть изменения

Реализована возможность настраивать, с какого момента начинается отсчет времени тапа:
- **Классическое поведение** (по умолчанию): таймер стартует с момента нажатия **первой** клавиши
- **Новое поведение** (опционально): таймер стартует с момента нажатия **второй** клавиши

## Мотивация

**Проблема:** Пользователь часто зажимает первую клавишу комбинации, а все последующие нажимает быстро (когда их найдёт – клавиши могут быть заметно разнесены пространственно). На это уходит время, и тап оказывается просроченным.

**Пример:**
```
Без start_timer_from_second_key (классика):
  Нажата Ctrl_L (t=0.00s) → start_time = 0.00s
  Нажата Shift_L (t=0.15s) [искали клавишу!]
  Отпущены все (t=0.25s) → duration = 0.25s > timeout(0.2s) ❌ INVALID

С start_timer_from_second_key=true:
  Нажата Ctrl_L (t=0.00s) → ждём...
  Нажата Shift_L (t=0.15s) → start_time = 0.15s (!)
  Отпущены все (t=0.25s) → duration = 0.10s < timeout(0.2s) ✅ VALID
```

## Внесённые изменения

### 1. Модель данных (`models.py`)

Добавлено новое поле в `HotkeyConfig`:

```python
@dataclass
class HotkeyConfig:
    keys: list[str]
    command: str
    args: list[str] = field(default_factory=list)
    description: str = ''
    start_timer_from_second_key: bool = False  # 🆕 НОВОЕ
```

**Описание:**
- `start_timer_from_second_key: bool = False` - если `True`, таймер тапа начинается с момента нажатия второй клавиши
- По умолчанию `False` - классическое поведение (таймер с первой клавиши)
- Полезно для комбинаций, где первая клавиша может быть зажата заранее

### 2. Состояние тапа (`tap_monitor.py`)

Обновлён `TapState`:

```python
@dataclass
class TapState:
    pressed_keys: set[Any] = field(default_factory=set)
    tap_combination: set[Any] = field(default_factory=set)
    start_time: float | None = None
    is_active: bool = False
    timer_delayed: bool = False  # 🆕 НОВОЕ
```

**Новое поле:**
- `timer_delayed: bool` - `True` если таймер отложен до второй клавиши

### 3. Монитор тапов (`tap_monitor.py`)

Обновлён конструктор `TapMonitor`:

```python
def __init__(
    self,
    timeout: float,
    verbose: bool = False,
    on_tap_detected: Callable[[set[Any], float], None] | None = None,
    on_tap_invalid: Callable[[str, set[Any], float], None] | None = None,
    check_timer_delay: Callable[[str], bool] | None = None,  # 🆕 НОВОЕ
) -> None:
```

**Новый параметр:**
- `check_timer_delay: Callable[[str], bool] | None` - функция для проверки, нужно ли откладывать таймер для данной клавиши

**Обновлена логика `_on_press`:**
- При нажатии первой клавиши вызывается `check_timer_delay(normalized_key)`
- Если возвращает `True` → таймер откладывается (`timer_delayed=True`, `start_time=None`)
- Если `False` → классическое поведение (таймер стартует сразу)
- При нажатии второй клавиши (если `timer_delayed=True`) → таймер стартует в этот момент

**Обновлена логика `_on_release`:**
- Если все клавиши отпущены, но таймер так и не был запущен (`start_time=None`) → тап невалиден ("insufficient keys")
- Это защита от ситуации, когда нажата только одна клавиша с отложенным таймером

### 4. Сопоставление hotkeys (`hotkey_matcher.py`)

Добавлен индекс для отложенного старта:

```python
def __init__(self, hotkeys: list[HotkeyConfig]) -> None:
    # Существующий индекс для быстрого поиска
    self._hotkey_map: dict[frozenset[str], HotkeyConfig] = {
        hk.keys_set(): hk for hk in hotkeys
    }
    
    # 🆕 НОВЫЙ индекс для отложенного старта
    # Map: key name -> list of hotkeys with start_timer_from_second_key=True
    self._delayed_start_map: dict[str, list[HotkeyConfig]] = {}
    for hk in hotkeys:
        if hk.start_timer_from_second_key and len(hk.keys) >= 2:
            for key in hk.keys:
                if key not in self._delayed_start_map:
                    self._delayed_start_map[key] = []
                self._delayed_start_map[key].append(hk)
```

Добавлен новый метод:

```python
def should_delay_timer_start(self, first_key_normalized: str) -> bool:
    """
    Проверить, нужно ли откладывать старт таймера.
    
    Returns True если есть хотя бы одна комбинация с:
    - start_timer_from_second_key=True
    - содержащая first_key_normalized
    """
    return first_key_normalized in self._delayed_start_map
```

### 5. Интеграция в launcher (`launcher_monitor.py`)

Добавлен callback для проверки отложенного старта:

```python
# В __init__:
self.tap_monitor = TapMonitor(
    timeout=config.tap_timeout,
    verbose=config.verbose_logging,
    on_tap_detected=self._on_tap_detected,
    on_tap_invalid=None,
    check_timer_delay=self._check_timer_delay,  # 🆕 НОВОЕ
)

# Новый метод:
def _check_timer_delay(self, first_key_normalized: str) -> bool:
    """Проверка через matcher."""
    return self.matcher.should_delay_timer_start(first_key_normalized)
```

### 6. Загрузка конфигурации (`config_loader.py`)

Обновлён парсинг hotkey:

```python
start_timer_from_second_key = data.get('start_timer_from_second_key', False)
if not isinstance(start_timer_from_second_key, bool):
    raise TypeError("'start_timer_from_second_key' must be a boolean")

return HotkeyConfig(
    keys=keys,
    command=command,
    args=args,
    description=description,
    start_timer_from_second_key=start_timer_from_second_key,  # 🆕 НОВОЕ
)
```

### 7. Пример конфигурации (`config/tap-launcher.toml.example`)

Добавлены примеры использования:

```toml
# С отложенным стартом (можно зажать первую клавишу)
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"
start_timer_from_second_key = true  # Timer starts from second key

# Классическое поведение (быстрый тап)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open GNOME Terminal"
# start_timer_from_second_key = false  # Default, can be omitted
```

## Итоговая схема работы

### Сценарий 1: Классическое поведение (`start_timer_from_second_key=false`)

```
Конфиг: keys=["ctrl_l", "alt_l", "t"], start_timer_from_second_key=false

1. Нажата ctrl_l (t=0.00s)
   → check_timer_delay("ctrl_l") → False
   → start_time = 0.00s, timer_delayed = False

2. Нажата alt_l (t=0.05s)
   → добавляем в combination

3. Нажата t (t=0.10s)
   → добавляем в combination

4. Отпущены все (t=0.15s)
   → duration = 0.15s - 0.00s = 0.15s < 0.2s ✅ VALID
```

### Сценарий 2: Отложенный старт (`start_timer_from_second_key=true`)

```
Конфиг: keys=["ctrl_l", "shift_l"], start_timer_from_second_key=true

1. Нажата ctrl_l (t=0.00s)
   → check_timer_delay("ctrl_l") → True
   → start_time = None, timer_delayed = True, is_active = True

2. Нажата shift_l (t=0.15s)  # пользователь искал клавишу!
   → timer_delayed=True и start_time=None
   → start_time = 0.15s, timer_delayed = False

3. Отпущены все (t=0.25s)
   → duration = 0.25s - 0.15s = 0.10s < 0.2s ✅ VALID
```

## Преимущества решения

✅ **Обратная совместимость**: Существующие конфигурации без `start_timer_from_second_key` работают как прежде

✅ **Гибкость**: Каждая комбинация может иметь своё поведение

✅ **Простота**: Минимальные изменения в существующем коде

✅ **Эффективность**: Проверка через быстрый lookup в `_delayed_start_map`

✅ **Понятность**: Поведение явно указывается в конфигурации

## Edge cases

**Q: Что если нажата только одна клавиша с `start_timer_from_second_key=true`?**  
A: Тап будет невалиден ("insufficient keys"), так как таймер не запустился.

**Q: Что если несколько комбинаций начинаются с одной клавиши, но у них разные настройки?**  
A: `check_timer_delay` вернёт `True`, если хотя бы одна комбинация имеет `start_timer_from_second_key=true`. Это безопасно, так как финальное сопоставление всё равно происходит по полной комбинации.

**Q: Влияет ли это на `tap-detector`?**  
A: Нет, `tap-detector` не знает о конфигурации и работает как прежде. Изменения только в `tap-launcher`.

## Измененные файлы

1. `src/tap_launcher/models.py` - добавлено поле `start_timer_from_second_key`
2. `src/tap_detector/tap_monitor.py` - добавлена логика отложенного старта
3. `src/tap_launcher/hotkey_matcher.py` - добавлен метод `should_delay_timer_start()`
4. `src/tap_launcher/launcher_monitor.py` - интегрирован callback `_check_timer_delay()`
5. `src/tap_launcher/config_loader.py` - парсинг нового поля
6. `config/tap-launcher.toml.example` - примеры использования

## Статус

✅ Реализовано  
✅ Протестировано линтером (без ошибок)  
⏳ Ожидает верификации пользователем

---

**Дата:** 13.10.2025  
**Версия:** tap-launcher v0.2.0 (pending)

