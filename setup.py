import os
import subprocess
import sys


def setup_project():
    """Настройка проекта: создание папок и онтологии"""

    # Создаем необходимые папки
    folders = [
        "ontology",
        "data",
        "src",
        "templates",
        "static/css",
        "static/js",
        "exports"
    ]

    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"✅ Создана папка: {folder}")

    # Запускаем создание онтологии
    print("\n🔄 Создание онтологии...")
    try:
        subprocess.run([sys.executable, "ontology/create_ontology.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при создании онтологии: {e}")
        return False

    print("\n✅ Проект успешно настроен!")
    print("\nДля запуска приложения выполните:")
    print("  python app.py")
    print("\nИ откройте в браузере:")
    print("  http://localhost:5000")

    return True


if __name__ == "__main__":
    setup_project()