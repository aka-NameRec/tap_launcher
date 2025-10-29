#!/usr/bin/env python3
"""
Тест перехвата RCtrl+Backspace с evdev + uinput.

Задача:
1. Перехватить комбинацию RCtrl+Backspace
2. Показать всплывающее сообщение
3. НЕ отдать событие в ОС
4. Отдать остальные клавиши в ОС

Подход: evdev для чтения, uinput для эмуляции
"""

import evdev
from evdev import UInput, ecodes as e
import subprocess
import sys
import os


def show_notification(message: str) -> None:
    """Показать всплывающее уведомление."""
    # Проверяем, запущено ли с sudo
    if os.getenv('SUDO_USER'):
        # Запускаем notify-send от имени обычного пользователя
        user = os.getenv('SUDO_USER')
        cmd = ['sudo', '-u', user, 'notify-send', 'Key Suppression Test', message]
        try:
            subprocess.run(cmd, check=False)
        except Exception:
            pass
    else:
        try:
            subprocess.run(['notify-send', 'Key Suppression Test', message], 
                          check=False)
        except Exception:
            pass
    print(f"\n🔔 {message}", file=sys.stderr)


def list_keyboard_devices():
    """Список всех возможных устройств клавиатуры."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    keyboards = []
    
    for device in devices:
        caps = device.capabilities()
        if e.EV_KEY in caps:
            keys = caps[e.EV_KEY]
            # Проверяем, что это клавиатура (есть буквы или модификаторы)
            if (e.KEY_A in keys or 
                e.KEY_LEFTCTRL in keys or 
                e.KEY_RIGHTCTRL in keys or
                e.KEY_BACKSPACE in keys):
                keyboards.append(device)
    
    return keyboards


def select_keyboard_interactive(keyboards):
    """Интерактивный выбор устройства клавиатуры."""
    if not keyboards:
        return None
    
    if len(keyboards) == 1:
        print("Найдено только одно устройство, используем его автоматически.\n")
        return keyboards[0]
    
    print("\nВыберите устройство (1-{}, или 'q' для выхода): ".format(len(keyboards)), end='')
    try:
        choice = input().strip()
        
        if choice.lower() == 'q':
            print("Выход...")
            return None
        
        index = int(choice) - 1
        if 0 <= index < len(keyboards):
            return keyboards[index]
        else:
            print("❌ Неверный выбор!")
            return None
    except (ValueError, KeyboardInterrupt):
        print("\n❌ Отмена...")
        return None


def main():
    print("=== Тест подавления RCtrl+Backspace через evdev ===\n")
    print("Поиск клавиатуры...\n")
    
    # Показываем все доступные клавиатуры
    keyboards = list_keyboard_devices()
    print(f"Найдено устройств клавиатуры: {len(keyboards)}\n")
    if keyboards:
        for i, dev in enumerate(keyboards, 1):
            name = dev.name
            is_virtual = 'uinput' in name.lower() or 'virtual' in name.lower()
            virtual_str = " [VIRTUAL]" if is_virtual else ""
            print(f"{i}. {name}{virtual_str}")
            print(f"   Путь: {dev.path}")
    else:
        print("❌ Клавиатура не найдена!")
        sys.exit(1)
    
    # Интерактивный выбор
    device = select_keyboard_interactive(keyboards)
    if not device:
        print("❌ Устройство не выбрано!")
        sys.exit(1)
    
    print(f"\n✅ Выбрана клавиатура: {device.name}")
    print(f"   Путь: {device.path}\n")
    
    # Захватываем устройство - теперь только мы получаем события
    device.grab()
    print("✅ Устройство захвачено\n")
    
    # Создаем виртуальное устройство для эмуляции
    capabilities = {
        e.EV_KEY: device.capabilities()[e.EV_KEY]
    }
    ui = UInput(capabilities)
    print("✅ Виртуальное устройство создано\n")
    
    print("Press RCtrl+Backspace to test suppression")
    print("Press Ctrl+C to exit\n")
    
    # Трекем нажатые клавиши
    pressed_keys = set()
    
    try:
        for event in device.read_loop():
            # Пропускаем неклавиатурные события
            if event.type != e.EV_KEY:
                continue
            
            # Эмулированные события имеют injected флаг или происходят от другого устройства
            # Но мы не можем их различить напрямую в evdev
            # Поэтому просто категоризуем и обрабатываем
            
            # Используем categorize для получения keycode
            try:
                key_event = evdev.categorize(event)
                
                # Проверяем, что keycode существует
                if not hasattr(key_event, 'keycode') or not key_event.keycode:
                    # Пропускаем события без keycode
                    continue
                
                keycode = key_event.keycode
            except Exception:
                # Ошибка категоризации - пропускаем событие
                continue
            
            # Состояние: key_down=press, key_up=release, key_hold=repeat
            if key_event.keystate == key_event.key_down:  # Press (value=1)
                pressed_keys.add(event.code)
                
                # Проверяем комбинацию RCtrl+Backspace
                if e.KEY_RIGHTCTRL in pressed_keys and e.KEY_BACKSPACE in pressed_keys:
                    show_notification("RCtrl+Backspace intercepted!")
                    pressed_keys.discard(event.code)
                    # НЕ эмулируем это событие обратно
                    continue
                
                # Эмулируем остальные события обратно в систему
                try:
                    ui.write(e.EV_KEY, event.code, event.value)
                    # НЕ вызываем syn() сразу
                except Exception:
                    pass
                
            elif key_event.keystate == key_event.key_up:  # Release (value=0)
                if event.code in pressed_keys:
                    pressed_keys.discard(event.code)
                
                # Проверяем, нужно ли подавить release Backspace при зажатом RCtrl
                if event.code == e.KEY_BACKSPACE and e.KEY_RIGHTCTRL in pressed_keys:
                    continue
                
                # Эмулируем release
                try:
                    ui.write(e.EV_KEY, event.code, event.value)
                    # Вызываем syn() ПОСЛЕ release
                    ui.syn()
                except Exception:
                    pass
                    
            elif key_event.keystate == key_event.key_hold:  # Repeat (value=2) - автоповтор
                # Для автоповтора эмулируем с syn(), чтобы повторения доходили
                try:
                    ui.write(e.EV_KEY, event.code, 2)  # key_hold
                    ui.syn()
                except Exception:
                    pass
    
    except KeyboardInterrupt:
        print("\n👋 Выход...")
    finally:
        device.ungrab()
        ui.close()


if __name__ == '__main__':
    main()

