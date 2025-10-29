#!/usr/bin/env python3
"""
Простой тест перехвата RCtrl+Backspace с pynput.

Задача:
1. Перехватить комбинацию RCtrl+Backspace
2. Показать всплывающее сообщение
3. НЕ отдать событие в ОС

Подход: suppress=False + return False для подавления конкретной комбинации
"""

from pynput import keyboard
import subprocess
import sys


def show_notification(message: str) -> None:
    """Показать всплывающее уведомление."""
    try:
        subprocess.run(['notify-send', 'Key Suppression Test', message], 
                      check=False)
    except Exception:
        # Если notify-send недоступен, вывести в stderr
        print(f"\n🔔 {message}", file=sys.stderr)


# Трекем состояние кнопок
pressed_keys = set()


def on_press(key, injected=False):
    """Обработка нажатия клавиши."""
    # Игнорируем свои собственные эмулированные события
    if injected:
        print(f"[IGNORED] Press: {key} (injected)")
        return True
        
    global pressed_keys
    
    pressed_keys.add(key)
    
    # Проверяем комбинацию: Right Control + Backspace
    ctrl_r = keyboard.Key.ctrl_r
    backspace = keyboard.Key.backspace
    
    # Проверяем, нужно ли подавить это событие
    if ctrl_r in pressed_keys and backspace in pressed_keys:
        show_notification("RCtrl+Backspace intercepted!")
        print("\n✅ RCtrl+Backspace перехвачено - событие НЕ будет передано в ОС")
        # Забываем о Backspace, чтобы не держать его нажатым
        pressed_keys.discard(backspace)
        # Подавляем это событие - не пропускаем в систему
        return False
    
    # С suppress=False просто пропускаем событие
    print(f"Press: {key}")
    return True  # Разрешаем событие пройти дальше


def on_release(key, injected=False):
    """Обработка отпускания клавиши."""
    # Игнорируем свои собственные эмулированные события
    if injected:
        print(f"[IGNORED] Release: {key} (injected)")
        return True
        
    global pressed_keys
    pressed_keys.discard(key)
    
    print(f"Release: {key}")
    
    # Проверяем комбинацию: Right Control + Backspace
    ctrl_r = keyboard.Key.ctrl_r
    backspace = keyboard.Key.backspace
    
    # Если это Backspace и уже зажат RCtrl - подавляем release
    if key == backspace and ctrl_r in pressed_keys:
        print("Release Backspace suppressed (RCtrl still pressed)")
        # Подавляем release
        return False
    
    # С suppress=False просто пропускаем событие
    print(f"Release: {key}")
    return True  # Разрешаем событие пройти дальше


def main():
    print("=== Тест подавления RCtrl+Backspace ===\n")
    print("Press RCtrl+Backspace to test suppression")
    print("Press Ctrl+C to exit\n")
    
    # Пробуем БЕЗ suppress=True
    # Это позволит событиям проходить в систему, но мы их все равно перехватываем
    listener = keyboard.Listener(
        on_press=on_press,
        on_release=on_release,
        suppress=False  # НЕ перехватываем всё, но можем реагировать
    )
    
    listener.start()
    
    try:
        listener.join()
    except KeyboardInterrupt:
        print("\n👋 Выход...")
        listener.stop()


if __name__ == '__main__':
    main()

