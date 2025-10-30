# Анализ: поддержка нескольких физических клавиатур

## Текущие ограничения

### Что мешает обрабатывать события от всех клавиатур:

1. **Архитектура backend**:
   - `self.device` - хранит только одно устройство
   - `device.read_loop()` - блокирующий цикл для одного устройства
   - Нет механизма для параллельного чтения из нескольких устройств

2. **device.grab()**:
   - Можно вызывать на нескольких устройствах одновременно
   - Каждое устройство нужно грабить отдельно
   - Не проблема для множественной обработки

3. **read_loop()**:
   - Это блокирующий генератор: `for event in device.read_loop()`
   - Можем читать только из одного устройства в синхронном цикле
   - Нужна многопоточность или async/select для нескольких устройств

4. **Uinput**:
   - Один uinput device может эмулировать события от разных источников
   - НЕ проблема для множественной обработки

5. **TapMonitor**:
   - Получает только Key/KeyCode объекты, не заботится об источнике
   - Может обрабатывать события от разных источников, если они объединены в один поток
   - НЕ проблема для множественной обработки

## Технически возможно

### Вариант 1: Threading (рекомендуется)

**Архитектура:**
```python
class EvdevBackend:
    def __init__(self):
        self.devices: list[InputDevice] = []  # Список вместо одного
        self.device_threads: list[threading.Thread] = []
        self.event_queue: queue.Queue = queue.Queue()
    
    def start(self, on_press, on_release):
        # Найти все физические клавиатуры
        keyboards = self._find_all_keyboard_devices()
        
        # Захватить все устройства
        for device in keyboards:
            device.grab()
            self.devices.append(device)
            
            # Запустить поток для чтения событий
            thread = threading.Thread(
                target=self._read_device_loop,
                args=(device,),
                daemon=True
            )
            thread.start()
            self.device_threads.append(thread)
        
        # Главный цикл: читать из очереди и обрабатывать
        while not self._stop_event.is_set():
            try:
                event_data = self.event_queue.get(timeout=0.1)
                device, event = event_data
                self._process_event(device, event, on_press, on_release)
            except queue.Empty:
                continue
    
    def _read_device_loop(self, device):
        """Поток для чтения событий из одного устройства."""
        for event in device.read_loop():
            if self._stop_event.is_set():
                break
            # Отправить в очередь для обработки
            self.event_queue.put((device, event))
```

**Преимущества:**
- ✅ Простая реализация
- ✅ События обрабатываются в порядке получения
- ✅ Можно определить источник события (device) если нужно
- ✅ Легко добавить/удалить устройство динамически

**Недостатки:**
- ⚠️ Потоки используют больше ресурсов
- ⚠️ Нужна синхронизация через queue

### Вариант 2: select/epoll

**Архитектура:**
```python
import select

class EvdevBackend:
    def start(self, on_press, on_release):
        keyboards = self._find_all_keyboard_devices()
        
        # Захватить все устройства
        for device in keyboards:
            device.grab()
            self.devices.append(device)
        
        # Использовать select для мониторинга файловых дескрипторов
        device_fds = {dev.fileno(): dev for dev in self.devices}
        
        while not self._stop_event.is_set():
            # Ждём события на любом из устройств
            ready, _, _ = select.select(device_fds.keys(), [], [], 0.1)
            
            for fd in ready:
                device = device_fds[fd]
                try:
                    # Читаем одно событие
                    for event in device.read():
                        self._process_event(device, event, on_press, on_release)
                        break  # Одно событие за раз
                except OSError:
                    # Устройство отключено
                    del device_fds[fd]
```

**Преимущества:**
- ✅ Один поток вместо нескольких
- ✅ Эффективнее по ресурсам
- ✅ Нативный способ для Linux

**Недостатки:**
- ⚠️ Более сложная реализация
- ⚠️ Нужен try/except для каждого устройства
- ⚠️ `device.read()` может заблокировать, нужен non-blocking режим

### Вариант 3: asyncio (для будущего)

Можно переписать на async/await, но это большая переработка.

## Проблемы, которые нужно решить

### 1. Отслеживание источника для suppression

**Проблема:** Если нужно подавить клавишу, мы должны знать, с какого устройства она пришла, чтобы правильно обработать.

**Решение:**
- Хранить mapping: `pressed_keycodes` → `(device, keycode)`
- При подавлении эмулировать только для конкретного устройства (но это не обязательно - один uinput может обработать всё)

### 2. Устройство отключается во время работы

**Проблема:** Клавиатура отключена/переподключена.

**Решение:**
- Обрабатывать OSError при чтении
- Удалять устройство из списка
- Возможно, добавить механизм переподключения

### 3. device.grab() на нескольких устройствах

**Вопрос:** Можем ли грабить все устройства одновременно?

**Ответ:** Да! `device.grab()` работает на уровне файлового дескриптора каждого устройства. Можно грабить сколько угодно устройств параллельно.

### 4. Uinput capabilities

**Вопрос:** Нужно ли создавать отдельный uinput для каждого устройства?

**Ответ:** Нет! Один uinput device может эмулировать события от любого количества физических устройств. Достаточно объединить capabilities всех устройств при создании uinput.

## Рекомендация

**Использовать threading подход:**

1. Проще реализовать
2. События обрабатываются последовательно через queue
3. Легко добавить логирование источника
4. TapMonitor не заботится об источнике - получает unified поток

**Изменения в архитектуре:**

```python
# Вместо:
self.device = InputDevice(...)

# Будет:
self.devices: list[InputDevice] = []
self.device_threads: list[threading.Thread] = []
self.event_queue: queue.Queue = queue.Queue(maxsize=1000)  # Защита от переполнения

# Вместо:
for event in self.device.read_loop():

# Будет:
while not self._stop_event.is_set():
    try:
        device, event = self.event_queue.get(timeout=0.1)
        # обработка
    except queue.Empty:
        continue
```

## Вывод

**Ничего фундаментального не мешает!** 

Технические ограничения - только в текущей архитектуре:
- Один `self.device` вместо списка
- Блокирующий `read_loop()` вместо параллельного чтения

Решение - использование threading или select для параллельного чтения из всех устройств с объединением событий в единый поток для TapMonitor.


