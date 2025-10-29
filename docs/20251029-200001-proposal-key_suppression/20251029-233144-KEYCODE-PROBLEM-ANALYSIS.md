# Анализ проблемы с пропуском клавиш `/`, `.`, `,`

## Проблема

При использовании `tap-launcher` клавиши `/`, `.`, `,` не передаются в другие приложения. В логах появляются сообщения:
```
Unknown keycode: KEY_SLASH (raw code: 53, value: 1). Skipping event.
Unknown keycode: KEY_DOT (raw code: 52, value: 1). Skipping event.
Unknown keycode: KEY_COMMA (raw code: 51, value: 1). Skipping event.
```

## Причина проблемы

### Цепочка событий:
1. **`device.grab()`** - перехватывает ВСЕ события с физической клавиатуры ДО того, как они попадают в систему
2. События читаются в цикле `device.read_loop()`
3. Происходит попытка конвертировать evdev keycode в pynput Key/KeyCode через `evdev_to_pynput_key()`
4. Для `KEY_SLASH`, `KEY_DOT`, `KEY_COMMA` маппинг отсутствует → `KeyError`
5. При `KeyError` выполняется `continue` - событие **полностью пропускается**
6. Событие **НЕ эмулируется** обратно через uinput
7. Система его **не получает** - клавиша не доходит до приложений

### Критическая ошибка в логике:

```python
# В evdev_backend.py:
try:
    pynput_key = evdev_to_pynput_key(key_event.keycode)
except KeyError:
    # Unknown key - log and skip
    self.logger.warning(...)
    continue  # ❌ ПРОБЛЕМА: событие теряется!
```

**Последствие**: Поскольку мы используем `device.grab()`, мы являемся единственным получателем событий. Если мы не эмулируем событие обратно через uinput, оно **теряется навсегда**.

## Почему это критично?

С `device.grab()`:
- События перехватываются **до** системы
- Мы обязаны эмулировать **все** события обратно
- Если событие не распознано → нужно всё равно эмулировать raw keycode

## Решение

### Вариант 1: Добавить маппинг для символьных клавиш (рекомендуется)

Добавить в `EVDEV_TO_PYNPUT_KEY`:
```python
'KEY_SLASH': KeyCode.from_char('/'),
'KEY_DOT': KeyCode.from_char('.'),
'KEY_COMMA': KeyCode.from_char(','),
'KEY_MINUS': KeyCode.from_char('-'),
'KEY_EQUAL': KeyCode.from_char('='),
'KEY_LEFTBRACE': KeyCode.from_char('['),
'KEY_RIGHTBRACE': KeyCode.from_char(']'),
'KEY_SEMICOLON': KeyCode.from_char(';'),
'KEY_APOSTROPHE': KeyCode.from_char("'"),
'KEY_BACKSLASH': KeyCode.from_char('\\'),
'KEY_GRAVE': KeyCode.from_char('`'),
# И другие символьные клавиши
```

**Преимущества:**
- ✅ Полная поддержка всех клавиш
- ✅ Корректная работа с tap detection
- ✅ Соответствие принципу "всё должно быть маппировано"

### Вариант 2: Fallback - эмулировать raw keycode даже для неизвестных

Когда keycode неизвестен, но есть raw keycode (число):
```python
except KeyError:
    # Unknown keycode - but we MUST emulate it back to system
    # because device.grab() means we intercepted it
    self.logger.warning(f'Unknown keycode: {key_event.keycode}, but emulating raw code {keycode}')
    
    # Emulate directly using raw keycode (don't try to call callbacks)
    if value == 1:  # Press
        self.uinput_device.write(ecodes.EV_KEY, keycode, 1)
        self.buffered_presses[keycode] = True
    elif value == 0:  # Release
        if keycode in self.buffered_presses:
            self.uinput_device.write(ecodes.EV_KEY, keycode, 0)
            self.uinput_device.syn()
            self.buffered_presses.pop(keycode, None)
    elif value == 2:  # Repeat
        self.uinput_device.write(ecodes.EV_KEY, keycode, 2)
        self.uinput_device.syn()
    continue  # Skip callback (can't convert to pynput)
```

**Преимущества:**
- ✅ Работает для всех клавиш
- ✅ Не нужно знать все возможные keycode'ы

**Недостатки:**
- ⚠️ Неизвестные клавиши не участвуют в tap detection
- ⚠️ Может быть проблема, если нужна нормализация для hotkey matching

### Вариант 3: Комбинированный подход (РЕКОМЕНДУЕТСЯ)

1. Добавить маппинг для всех распространённых символьных клавиш
2. Для оставшихся неизвестных - использовать fallback эмуляцию через raw keycode

**Преимущества:**
- ✅ Максимальная поддержка
- ✅ Неизвестные клавиши всё равно работают
- ✅ Распространённые клавиши работают в tap detection

## Рекомендация

**Использовать Вариант 3** - комбинированный подход:
1. Расширить `EVDEV_TO_PYNPUT_KEY` всеми символьными клавишами
2. Добавить fallback логику для неизвестных keycode'ов с обязательной эмуляцией через raw keycode

## Дополнительные замечания

### Почему маппинг неполный?

Текущая логика в `evdev_to_pynput_key()` поддерживает только:
- Буквы: `KEY_A` ... `KEY_Z` (через проверку `len == 5` и `isalpha()`)
- Цифры: `KEY_0` ... `KEY_9` (через проверку `len == 5` и `isdigit()`)
- Специальные клавиши: явный маппинг в `EVDEV_TO_PYNPUT_KEY`

**Не поддерживаются:**
- Символьные клавиши: `/`, `.`, `,`, `-`, `=`, `[`, `]`, `;`, `'`, `\`, `` ` ``
- Numpad символы (кроме частично замапленных через KP*)

### Список пропущенных символьных клавиш:

```python
# Основные символы (кроме букв и цифр):
KEY_SLASH = 53      # '/'
KEY_DOT = 52        # '.'
KEY_COMMA = 51      # ','
KEY_MINUS = 12      # '-'
KEY_EQUAL = 13      # '='
KEY_LEFTBRACE = 26  # '['
KEY_RIGHTBRACE = 27 # ']'
KEY_SEMICOLON = 39  # ';'
KEY_APOSTROPHE = 40 # "'"
KEY_BACKSLASH = 43  # '\'
KEY_GRAVE = 41      # '`'
```

Эти клавиши нужно добавить в маппинг.

