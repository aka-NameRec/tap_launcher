# Изменение определения тапа в приложении
_Exported on 13.10.2025 at 16:23:25 GMT+3 from Cursor (1.7.44)_

---

**User**

(20251013-160723)
(0) Ознакомься со структурой нашего приложения, изучи `README.md` в корне проекта, и документы по ссылкам.
Давай попробуем изменить определение тапа.

(1) Фабула: пользователь яасто зажимает первую клавишу комбинации, а все последующие нажимает быстро (когда их найдёт – клавиши могут быть заметно разнесены пространственно). На это уходит время, и тап оказывается просроченным.

(2) Давай учтём это и, если комбинацию не удалось идентифицировать по первой клавише, мы её продолжаем помнить, но время тапа оначинаем счиать с момента нажатия на вторую клавишу комбинации.

(3) Поведение, описанное в (2) должно быть свойством комбинации: нужно иметь возможность указать: считать ли тап по данной комбинации с первой клавиши, или со второй.

—
Предложи техническое решение. Код писать пока ненужно.

---

**Cursor**

Изучу структуру проекта и документацию, чтобы предложить техническое решение.

Изучу дополнительные документы для полного понимания реализации.

Отлично, изучил структуру проекта и текущую реализацию. Предложу техническое решение для изменения определения тапа.

## 📋 Техническое решение: Гибкий старт таймера тапа

### **Суть проблемы**

**Текущее поведение:**
```
Нажата Ctrl_L (t=0.00s) → start_time = 0.00s
Нажата Shift_L (t=0.15s)
Отпущены все (t=0.25s) → duration = 0.25s > timeout(0.2s) ❌ INVALID
```

**Желаемое поведение (для некоторых комбинаций):**
```
Нажата Ctrl_L (t=0.00s) → ждём...
Нажата Shift_L (t=0.15s) → start_time = 0.15s (!)
Отпущены все (t=0.25s) → duration = 0.10s < timeout(0.2s) ✅ VALID
```

---

### **1. Расширение модели конфигурации**

**Файл: `src/tap_launcher/models.py`**

Добавить новое свойство в `HotkeyConfig`:

```python
@dataclass
class HotkeyConfig:
    keys: list[str]
    command: str
    args: list[str] = field(default_factory=list)
    description: str = ''
    
    # 🆕 НОВОЕ СВОЙСТВО
    start_timer_from_second_key: bool = False
    """
    Если True, таймер тапа начинается с момента нажатия ВТОРОЙ клавиши.
    Полезно для комбинаций, где первая клавиша может быть зажата заранее.
    
    Примеры:
    - False (по умолчанию): классическое поведение, таймер с первой клавиши
    - True: таймер начинается со второй клавиши
    """
```

**Пример конфигурации:**

```toml
# Классическое поведение (быстрые тапы)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
start_timer_from_second_key = false  # или не указывать (default)

# Новое поведение (можно зажать Ctrl_L, потом искать Shift_L)
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
start_timer_from_second_key = true  # таймер со второй клавиши
```

---

### **2. Изменения в HotkeyMatcher**

**Файл: `src/tap_launcher/hotkey_matcher.py`**

Добавить метод для проверки "частичного совпадения":

```python
class HotkeyMatcher:
    def __init__(self, hotkeys: list[HotkeyConfig]) -> None:
        self._hotkey_map: dict[frozenset[str], HotkeyConfig] = {
            hk.keys_set(): hk for hk in hotkeys
        }
        
        # 🆕 Дополнительный индекс для отложенного старта
        # Мапа: первая клавиша → список hotkeys с start_timer_from_second_key=True
        self._delayed_start_map: dict[str, list[HotkeyConfig]] = {}
        for hk in hotkeys:
            if hk.start_timer_from_second_key and len(hk.keys) >= 2:
                # Для каждой клавиши в комбинации
                for key in hk.keys:
                    if key not in self._delayed_start_map:
                        self._delayed_start_map[key] = []
                    self._delayed_start_map[key].append(hk)
    
    def match(self, detected_keys: set[Any]) -> HotkeyConfig | None:
        """Существующий метод - без изменений."""
        ...
    
    # 🆕 НОВЫЙ МЕТОД
    def should_delay_timer_start(
        self, 
        first_key_normalized: str
    ) -> bool:
        """
        Проверить, нужно ли откладывать старт таймера.
        
        Возвращает True, если:
        - Есть хотя бы одна комбинация с start_timer_from_second_key=True
        - Эта комбинация начинается с first_key_normalized
        
        Args:
            first_key_normalized: Нормализованное имя первой нажатой клавиши
            
        Returns:
            bool: True если нужно откладывать старт таймера
        """
        return first_key_normalized in self._delayed_start_map
```

---

### **3. Изменения в TapMonitor**

**Файл: `src/tap_detector/tap_monitor.py`**

Модифицировать логику для поддержки отложенного старта:

```python
@dataclass
class TapState:
    pressed_keys: set = field(default_factory=set)
    tap_combination: set = field(default_factory=set)
    start_time: float | None = None
    is_active: bool = False
    
    # 🆕 НОВОЕ ПОЛЕ
    timer_delayed: bool = False
    """True если таймер отложен до второй клавиши."""

class TapMonitor:
    def __init__(
        self,
        timeout: float,
        verbose: bool = False,
        on_tap_detected: Callable | None = None,
        on_tap_invalid: Callable | None = None,
        # 🆕 НОВЫЙ ПАРАМЕТР
        check_timer_delay: Callable[[str], bool] | None = None,
    ):
        """
        Args:
            ...существующие параметры...
            check_timer_delay: Функция для проверки, нужно ли откладывать
                             таймер для данной клавиши.
                             Принимает: normalized_key_name (str)
                             Возвращает: bool (True = отложить старт)
        """
        self.timeout = timeout
        self.verbose = verbose
        self.state = TapState()
        self.on_tap_detected = on_tap_detected
        self.on_tap_invalid = on_tap_invalid
        self.check_timer_delay = check_timer_delay
    
    def _on_press(self, key):
        # Игнорируем автоповтор
        if key in self.state.pressed_keys:
            return
        
        # Первая клавиша?
        if not self.state.is_active:
            normalized_key = normalize_key(key)
            
            # 🆕 ПРОВЕРКА НА ОТЛОЖЕННЫЙ СТАРТ
            if self.check_timer_delay and self.check_timer_delay(normalized_key):
                # Откладываем старт таймера
                self.state.is_active = True
                self.state.timer_delayed = True
                self.state.start_time = None  # пока не запускаем таймер
                
                if self.verbose:
                    print(f"[TRACE] First key {normalized_key}, timer delayed")
            else:
                # Классическое поведение - стартуем таймер сразу
                self.state.start_time = perf_counter()
                self.state.is_active = True
                
                if self.verbose:
                    print(f"[TRACE] Tap started with {normalized_key}")
        
        # Вторая (или последующая) клавиша?
        else:
            # 🆕 Если таймер был отложен, запускаем его СЕЙЧАС
            if self.state.timer_delayed and self.state.start_time is None:
                self.state.start_time = perf_counter()
                self.state.timer_delayed = False
                
                if self.verbose:
                    normalized_key = normalize_key(key)
                    print(f"[TRACE] Second key {normalized_key}, timer started NOW")
        
        # Добавляем клавишу
        self.state.pressed_keys.add(key)
        self.state.tap_combination.add(key)
        
        # Проверка timeout (только если таймер уже запущен)
        if self.state.start_time:
            elapsed = perf_counter() - self.state.start_time
            if elapsed > self.timeout:
                if self.verbose:
                    print(f"[TRACE] Timeout exceeded: {elapsed:.3f}s")
    
    def _on_release(self, key):
        """Логика без изменений - проверяем duration как обычно."""
        if key in self.state.pressed_keys:
            self.state.pressed_keys.remove(key)
        
        # Все клавиши отпущены?
        if not self.state.pressed_keys and self.state.is_active:
            # 🆕 Если таймер так и не был запущен (только 1 клавиша нажата)
            if self.state.start_time is None:
                # Это недопустимо - комбинация требует минимум 2 клавиши
                if self.verbose:
                    print("[DEBUG] Tap invalid: only one key pressed")
                if self.on_tap_invalid:
                    self.on_tap_invalid(
                        "insufficient keys", 
                        self.state.tap_combination.copy(), 
                        0.0
                    )
                self.state.reset()
                return
            
            # Обычная валидация
            end_time = perf_counter()
            duration = end_time - self.state.start_time
            
            is_valid = duration <= self.timeout
            
            if is_valid:
                if self.on_tap_detected:
                    self.on_tap_detected(
                        self.state.tap_combination.copy(), 
                        duration
                    )
            else:
                if self.on_tap_invalid:
                    self.on_tap_invalid(
                        "timeout exceeded", 
                        self.state.tap_combination.copy(), 
                        duration
                    )
            
            self.state.reset()
```

---

### **4. Интеграция в LauncherMonitor**

**Файл: `src/tap_launcher/launcher_monitor.py`**

Передать callback для проверки отложенного старта:

```python
class LauncherMonitor:
    def __init__(
        self,
        config: AppConfig,
        matcher: HotkeyMatcher,
        executor: CommandExecutor,
    ) -> None:
        self.config = config
        self.matcher = matcher
        self.executor = executor
        self.logger = logging.getLogger('tap_launcher.monitor')
        
        # 🆕 Создаём TapMonitor с callback для проверки отложенного старта
        self.tap_monitor = TapMonitor(
            timeout=config.tap_timeout,
            verbose=config.verbose_logging,
            on_tap_detected=self._on_tap_detected,
            on_tap_invalid=None,
            # 🆕 НОВЫЙ ПАРАМЕТР
            check_timer_delay=self._check_timer_delay,
        )
    
    # 🆕 НОВЫЙ МЕТОД
    def _check_timer_delay(self, first_key_normalized: str) -> bool:
        """
        Проверить, нужно ли откладывать старт таймера для данной клавиши.
        
        Этот callback вызывается TapMonitor при нажатии первой клавиши.
        
        Args:
            first_key_normalized: Нормализованное имя первой клавиши
            
        Returns:
            bool: True если есть комбинация с отложенным стартом
        """
        return self.matcher.should_delay_timer_start(first_key_normalized)
```

---

### **5. Обновление конфигурации**

**Файл: `config/tap-launcher.toml.example`**

```toml
# Пример 1: Классическое поведение (быстрый тап)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open terminal"
# start_timer_from_second_key не указан = false (по умолчанию)

# Пример 2: Отложенный старт (можно зажать первую клавишу)
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"
start_timer_from_second_key = true  # 🆕 таймер со второй клавиши

[[hotkeys]]
keys = ["ctrl_r", "shift_r"]
command = "setxkbmap"
args = ["ru"]
description = "Switch to Russian layout"
start_timer_from_second_key = true  # 🆕 таймер со второй клавиши
```

---

### **6. Изменения в ConfigLoader**

**Файл: `src/tap_launcher/config_loader.py`**

Добавить парсинг нового поля:

```python
@staticmethod
def _parse_hotkey(hotkey_data: dict) -> HotkeyConfig:
    """Parse a single hotkey from config data."""
    return HotkeyConfig(
        keys=hotkey_data['keys'],
        command=hotkey_data['command'],
        args=hotkey_data.get('args', []),
        description=hotkey_data.get('description', ''),
        # 🆕 НОВОЕ ПОЛЕ
        start_timer_from_second_key=hotkey_data.get(
            'start_timer_from_second_key', 
            False
        ),
    )
```

---

## **Итоговая схема работы**

### **Сценарий 1: Классическое поведение (`start_timer_from_second_key=false`)**

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

### **Сценарий 2: Отложенный старт (`start_timer_from_second_key=true`)**

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

---

## **Преимущества решения**

✅ **Обратная совместимость**: Существующие конфигурации без `start_timer_from_second_key` работают как прежде

✅ **Гибкость**: Каждая комбинация может иметь своё поведение

✅ **Простота**: Минимальные изменения в существующем коде

✅ **Эффективность**: Проверка через быстрый lookup в `_delayed_start_map`

✅ **Понятность**: Поведение явно указывается в конфигурации

---

## **Edge cases**

**Q: Что если нажата только одна клавиша с `start_timer_from_second_key=true`?**  
A: Тап будет невалиден ("insufficient keys"), так как таймер не запустился.

**Q: Что если несколько комбинаций начинаются с одной клавиши, но у них разные настройки?**  
A: `check_timer_delay` вернёт `True`, если хотя бы одна комбинация имеет `start_timer_from_second_key=true`. Это безопасно, так как финальное сопоставление всё равно происходит по полной комбинации.

**Q: Влияет ли это на `tap-detector`?**  
A: Нет, `tap-detector` не знает о конфигурации и работает как прежде. Изменения только в `tap-launcher`.

---

Это полное техническое решение. Готов обсудить детали или уточнения! 🚀

```plaintext
Нажата Ctrl_L (t=0.00s) → start_time = 0.00s
Нажата Shift_L (t=0.15s)
Отпущены все (t=0.25s) → duration = 0.25s > timeout(0.2s) ❌ INVALID
```

```plaintext
Нажата Ctrl_L (t=0.00s) → ждём...
Нажата Shift_L (t=0.15s) → start_time = 0.15s (!)
Отпущены все (t=0.25s) → duration = 0.10s < timeout(0.2s) ✅ VALID
```

```python
@dataclass
class HotkeyConfig:
    keys: list[str]
    command: str
    args: list[str] = field(default_factory=list)
    description: str = ''
    
    # 🆕 НОВОЕ СВОЙСТВО
    start_timer_from_second_key: bool = False
    """
    Если True, таймер тапа начинается с момента нажатия ВТОРОЙ клавиши.
    Полезно для комбинаций, где первая клавиша может быть зажата заранее.
    
    Примеры:
    - False (по умолчанию): классическое поведение, таймер с первой клавиши
    - True: таймер начинается со второй клавиши
    """
```

```toml
# Классическое поведение (быстрые тапы)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
start_timer_from_second_key = false  # или не указывать (default)

# Новое поведение (можно зажать Ctrl_L, потом искать Shift_L)
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
start_timer_from_second_key = true  # таймер со второй клавиши
```

```python
class HotkeyMatcher:
    def __init__(self, hotkeys: list[HotkeyConfig]) -> None:
        self._hotkey_map: dict[frozenset[str], HotkeyConfig] = {
            hk.keys_set(): hk for hk in hotkeys
        }
        
        # 🆕 Дополнительный индекс для отложенного старта
        # Мапа: первая клавиша → список hotkeys с start_timer_from_second_key=True
        self._delayed_start_map: dict[str, list[HotkeyConfig]] = {}
        for hk in hotkeys:
            if hk.start_timer_from_second_key and len(hk.keys) >= 2:
                # Для каждой клавиши в комбинации
                for key in hk.keys:
                    if key not in self._delayed_start_map:
                        self._delayed_start_map[key] = []
                    self._delayed_start_map[key].append(hk)
    
    def match(self, detected_keys: set[Any]) -> HotkeyConfig | None:
        """Существующий метод - без изменений."""
        ...
    
    # 🆕 НОВЫЙ МЕТОД
    def should_delay_timer_start(
        self, 
        first_key_normalized: str
    ) -> bool:
        """
        Проверить, нужно ли откладывать старт таймера.
        
        Возвращает True, если:
        - Есть хотя бы одна комбинация с start_timer_from_second_key=True
        - Эта комбинация начинается с first_key_normalized
        
        Args:
            first_key_normalized: Нормализованное имя первой нажатой клавиши
            
        Returns:
            bool: True если нужно откладывать старт таймера
        """
        return first_key_normalized in self._delayed_start_map
```

```python
@dataclass
class TapState:
    pressed_keys: set = field(default_factory=set)
    tap_combination: set = field(default_factory=set)
    start_time: float | None = None
    is_active: bool = False
    
    # 🆕 НОВОЕ ПОЛЕ
    timer_delayed: bool = False
    """True если таймер отложен до второй клавиши."""

class TapMonitor:
    def __init__(
        self,
        timeout: float,
        verbose: bool = False,
        on_tap_detected: Callable | None = None,
        on_tap_invalid: Callable | None = None,
        # 🆕 НОВЫЙ ПАРАМЕТР
        check_timer_delay: Callable[[str], bool] | None = None,
    ):
        """
        Args:
            ...существующие параметры...
            check_timer_delay: Функция для проверки, нужно ли откладывать
                             таймер для данной клавиши.
                             Принимает: normalized_key_name (str)
                             Возвращает: bool (True = отложить старт)
        """
        self.timeout = timeout
        self.verbose = verbose
        self.state = TapState()
        self.on_tap_detected = on_tap_detected
        self.on_tap_invalid = on_tap_invalid
        self.check_timer_delay = check_timer_delay
    
    def _on_press(self, key):
        # Игнорируем автоповтор
        if key in self.state.pressed_keys:
            return
        
        # Первая клавиша?
        if not self.state.is_active:
            normalized_key = normalize_key(key)
            
            # 🆕 ПРОВЕРКА НА ОТЛОЖЕННЫЙ СТАРТ
            if self.check_timer_delay and self.check_timer_delay(normalized_key):
                # Откладываем старт таймера
                self.state.is_active = True
                self.state.timer_delayed = True
                self.state.start_time = None  # пока не запускаем таймер
                
                if self.verbose:
                    print(f"[TRACE] First key {normalized_key}, timer delayed")
            else:
                # Классическое поведение - стартуем таймер сразу
                self.state.start_time = perf_counter()
                self.state.is_active = True
                
                if self.verbose:
                    print(f"[TRACE] Tap started with {normalized_key}")
        
        # Вторая (или последующая) клавиша?
        else:
            # 🆕 Если таймер был отложен, запускаем его СЕЙЧАС
            if self.state.timer_delayed and self.state.start_time is None:
                self.state.start_time = perf_counter()
                self.state.timer_delayed = False
                
                if self.verbose:
                    normalized_key = normalize_key(key)
                    print(f"[TRACE] Second key {normalized_key}, timer started NOW")
        
        # Добавляем клавишу
        self.state.pressed_keys.add(key)
        self.state.tap_combination.add(key)
        
        # Проверка timeout (только если таймер уже запущен)
        if self.state.start_time:
            elapsed = perf_counter() - self.state.start_time
            if elapsed > self.timeout:
                if self.verbose:
                    print(f"[TRACE] Timeout exceeded: {elapsed:.3f}s")
    
    def _on_release(self, key):
        """Логика без изменений - проверяем duration как обычно."""
        if key in self.state.pressed_keys:
            self.state.pressed_keys.remove(key)
        
        # Все клавиши отпущены?
        if not self.state.pressed_keys and self.state.is_active:
            # 🆕 Если таймер так и не был запущен (только 1 клавиша нажата)
            if self.state.start_time is None:
                # Это недопустимо - комбинация требует минимум 2 клавиши
                if self.verbose:
                    print("[DEBUG] Tap invalid: only one key pressed")
                if self.on_tap_invalid:
                    self.on_tap_invalid(
                        "insufficient keys", 
                        self.state.tap_combination.copy(), 
                        0.0
                    )
                self.state.reset()
                return
            
            # Обычная валидация
            end_time = perf_counter()
            duration = end_time - self.state.start_time
            
            is_valid = duration <= self.timeout
            
            if is_valid:
                if self.on_tap_detected:
                    self.on_tap_detected(
                        self.state.tap_combination.copy(), 
                        duration
                    )
            else:
                if self.on_tap_invalid:
                    self.on_tap_invalid(
                        "timeout exceeded", 
                        self.state.tap_combination.copy(), 
                        duration
                    )
            
            self.state.reset()
```

```python
class LauncherMonitor:
    def __init__(
        self,
        config: AppConfig,
        matcher: HotkeyMatcher,
        executor: CommandExecutor,
    ) -> None:
        self.config = config
        self.matcher = matcher
        self.executor = executor
        self.logger = logging.getLogger('tap_launcher.monitor')
        
        # 🆕 Создаём TapMonitor с callback для проверки отложенного старта
        self.tap_monitor = TapMonitor(
            timeout=config.tap_timeout,
            verbose=config.verbose_logging,
            on_tap_detected=self._on_tap_detected,
            on_tap_invalid=None,
            # 🆕 НОВЫЙ ПАРАМЕТР
            check_timer_delay=self._check_timer_delay,
        )
    
    # 🆕 НОВЫЙ МЕТОД
    def _check_timer_delay(self, first_key_normalized: str) -> bool:
        """
        Проверить, нужно ли откладывать старт таймера для данной клавиши.
        
        Этот callback вызывается TapMonitor при нажатии первой клавиши.
        
        Args:
            first_key_normalized: Нормализованное имя первой клавиши
            
        Returns:
            bool: True если есть комбинация с отложенным стартом
        """
        return self.matcher.should_delay_timer_start(first_key_normalized)
```

```toml
# Пример 1: Классическое поведение (быстрый тап)
[[hotkeys]]
keys = ["ctrl_l", "alt_l", "t"]
command = "gnome-terminal"
args = []
description = "Open terminal"
# start_timer_from_second_key не указан = false (по умолчанию)

# Пример 2: Отложенный старт (можно зажать первую клавишу)
[[hotkeys]]
keys = ["ctrl_l", "shift_l"]
command = "setxkbmap"
args = ["us"]
description = "Switch to English layout"
start_timer_from_second_key = true  # 🆕 таймер со второй клавиши

[[hotkeys]]
keys = ["ctrl_r", "shift_r"]
command = "setxkbmap"
args = ["ru"]
description = "Switch to Russian layout"
start_timer_from_second_key = true  # 🆕 таймер со второй клавиши
```

```python
@staticmethod
def _parse_hotkey(hotkey_data: dict) -> HotkeyConfig:
    """Parse a single hotkey from config data."""
    return HotkeyConfig(
        keys=hotkey_data['keys'],
        command=hotkey_data['command'],
        args=hotkey_data.get('args', []),
        description=hotkey_data.get('description', ''),
        # 🆕 НОВОЕ ПОЛЕ
        start_timer_from_second_key=hotkey_data.get(
            'start_timer_from_second_key', 
            False
        ),
    )
```

```plaintext
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

```plaintext
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

