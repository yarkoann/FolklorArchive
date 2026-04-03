from flask import Flask, render_template, request, jsonify, send_file
from src.metadata_manager import FolklorMetadataManager
from datetime import datetime
import json
import os
import csv
import traceback
import uuid
from rdflib.namespace import RDF, RDFS

app = Flask(__name__)

# Определяем пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ONTOLOGY_PATH = os.path.join(BASE_DIR, "ontology", "folklor_ontology.owl")
DATA_PATH = os.path.join(BASE_DIR, "data", "recordings.json")  # Изменено на .json
VOCAB_PATH = os.path.join(BASE_DIR, "data", "controlled_vocabulary.json")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

# Создаем папку для экспорта
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Инициализируем менеджер
manager = FolklorMetadataManager(ontology_path=ONTOLOGY_PATH)


def load_vocabulary():
    """Загрузка контролируемого словаря"""
    if os.path.exists(VOCAB_PATH):
        with open(VOCAB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'ethnos': [],
        'genres': [],
        'locations': [],
        'collections': [],
        'instruments': [],
        'ritual_status': []
    }


def ensure_json_exists():
    """Создание JSON файла если его нет"""
    if not os.path.exists(DATA_PATH):
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        initial_data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'total_recordings': 0,
            'recordings': []
        }
        with open(DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Создан новый JSON файл: {DATA_PATH}")


def load_existing_data():
    """Загрузка существующих данных из JSON в RDF граф"""
    if not os.path.exists(DATA_PATH):
        ensure_json_exists()
        return

    # Проверяем, есть ли уже записи в графе
    existing = manager.get_all_recordings()
    if existing:
        print(f"📊 В графе уже есть {len(existing)} записей, пропускаем загрузку из JSON")
        return

    print(f"\n{'=' * 60}")
    print(f"📂 ЗАГРУЗКА ДАННЫХ ИЗ JSON")
    print(f"{'=' * 60}")

    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            recordings = data.get('recordings', [])

        print(f"Найдено записей в JSON: {len(recordings)}")

        count = 0
        for rec in recordings:
            if not rec.get('title'):
                continue

            print(f"\n📄 Загрузка: {rec.get('title')}")

            # Проверяем формат исполнителей
            performers = rec.get('performers', [])
            if isinstance(performers, str):
                performers = [{'name': performers, 'ethnos': rec.get('ethnos', '')}]

            # Подготавливаем данные для add_recording (не используем _add_to_rdf_graph)
            recording_data = {
                'title': rec.get('title', ''),
                'inventory_number': rec.get('inventory_number', ''),
                'recording_date': rec.get('recording_date', ''),
                'duration': rec.get('duration', ''),
                'performers': performers,
                'genre': rec.get('genre', ''),
                'ethical_status': rec.get('ethical_status', ''),
                'location': rec.get('location', ''),
                'collection': rec.get('collection', ''),
                'local_terms': rec.get('local_terms', []),
                'description': rec.get('description', '')
            }

            # Используем add_recording вместо прямого вызова _add_to_rdf_graph
            manager.add_recording(recording_data)
            print(f"   ✅ Запись добавлена в RDF")
            count += 1

        print(f"\n✅ Загружено {count} записей из JSON в RDF граф")

        # Сохраняем граф
        manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
        print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        traceback.print_exc()


def save_to_json(recording_data, recording_id=None):
    """Сохранение записи в JSON файл (ЕДИНСТВЕННОЕ ХРАНИЛИЩЕ)"""
    json_path = DATA_PATH

    # Загружаем существующие записи
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            recordings = data.get('recordings', [])
    else:
        data = {'version': '1.0', 'recordings': []}
        recordings = []

    # Если ID не указан, генерируем новый
    if not recording_id:
        recording_id = f"rec_{uuid.uuid4().hex[:8]}"

    # Проверяем, существует ли уже запись с таким ID
    existing_index = None
    for i, rec in enumerate(recordings):
        if rec.get('id') == recording_id:
            existing_index = i
            break

    # Создаем объект записи
    new_recording = {
        'id': recording_id,
        'title': recording_data.get('title', ''),
        'inventory_number': recording_data.get('inventory_number', ''),
        'recording_date': recording_data.get('recording_date', ''),
        'duration': recording_data.get('duration', ''),
        'performers': recording_data.get('performers', []),
        'genre': recording_data.get('genre', ''),
        'ethical_status': recording_data.get('ethical_status', ''),
        'location': recording_data.get('location', ''),
        'collection': recording_data.get('collection', ''),
        'local_terms': recording_data.get('local_terms', []),
        'description': recording_data.get('description', ''),
        'updated_at': datetime.now().isoformat()
    }

    # Добавляем created_at только для новой записи
    if existing_index is None:
        new_recording['created_at'] = datetime.now().isoformat()
        recordings.append(new_recording)
        print(f"✅ Добавлена новая запись в JSON: {recording_id}")
    else:
        # Сохраняем original created_at
        if 'created_at' in recordings[existing_index]:
            new_recording['created_at'] = recordings[existing_index]['created_at']
        recordings[existing_index] = new_recording
        print(f"✅ Обновлена запись в JSON: {recording_id}")

    # Сохраняем обратно в JSON (ТОЛЬКО ОДИН ФАЙЛ)
    data = {
        'version': '1.0',
        'last_updated': datetime.now().isoformat(),
        'total_recordings': len(recordings),
        'recordings': recordings
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON сохранен. Всего записей: {len(recordings)}")
    return recording_id


def delete_from_json(recording_id):
    """Удаление записи из JSON файла"""
    json_path = DATA_PATH

    if not os.path.exists(json_path):
        print(f"⚠️ JSON файл не найден: {json_path}")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        recordings = data.get('recordings', [])

    deleted = False
    new_recordings = []
    for rec in recordings:
        if rec.get('id') == recording_id:
            print(f"✅ Найдена запись для удаления: {rec.get('title')}")
            deleted = True
            # Не добавляем эту запись в новый список
        else:
            new_recordings.append(rec)

    if deleted:
        data['recordings'] = new_recordings
        data['last_updated'] = datetime.now().isoformat()
        data['total_recordings'] = len(new_recordings)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Запись {recording_id} удалена из JSON")
        return True
    else:
        print(f"⚠️ Запись {recording_id} не найдена в JSON")
        return False


# Загружаем существующие данные
ensure_json_exists()
load_existing_data()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/add_recording')
def add_recording_page():
    return render_template('add_recording.html')


@app.route('/edit_recording/<recording_id>')
def edit_recording_page(recording_id):
    return render_template('edit_recording.html', recording_id=recording_id)


@app.route('/recording/<recording_id>')
def recording_detail(recording_id):
    return render_template('recording_detail.html', recording_id=recording_id)


@app.route('/search')
def search_page():
    return render_template('search.html')


@app.route('/api/facet_search')
def api_facet_search():
    filters = {}

    if request.args.get('ethnos'):
        filters['ethnos'] = request.args.get('ethnos')
    if request.args.get('genre'):
        filters['genre'] = request.args.get('genre')
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('location'):
        filters['location'] = request.args.get('location')
    if request.args.get('collection'):
        filters['collection'] = request.args.get('collection')
    if request.args.get('decade'):
        filters['decade'] = request.args.get('decade')
    if request.args.get('q'):
        filters['search'] = request.args.get('q')

    page = int(request.args.get('page', 1))
    sort = request.args.get('sort', 'title')

    print(f"🔥 API получены фильтры: {filters}")
    results = manager.facet_search(filters=filters, page=page, sort=sort)
    return jsonify(results)


@app.route('/api/facets')
def api_facets():
    facets = manager.get_facet_counts()
    return jsonify(facets)


@app.route('/api/add_recording', methods=['POST'])
def api_add_recording():
    """API для добавления записи"""
    try:
        data = request.json
        print("\n" + "=" * 60)
        print("📥 ПОЛУЧЕНЫ ДАННЫЕ ДЛЯ ДОБАВЛЕНИЯ:")
        print("=" * 60)
        print(f"Title: {data.get('title')}")
        print(f"Genre: {data.get('genre')}")
        print(f"Location: {data.get('location')}")
        print(f"Collection: {data.get('collection')}")
        print(f"Ethical status: {data.get('ethical_status')}")

        # Детальный вывод исполнителей
        print("\n👥 ИСПОЛНИТЕЛИ:")
        performers = data.get('performers', [])
        if performers:
            for i, p in enumerate(performers):
                print(f"  {i + 1}. Имя: '{p.get('name')}', Этнос: '{p.get('ethnos')}'")
        else:
            print("  ❌ НЕТ ДАННЫХ ОБ ИСПОЛНИТЕЛЯХ!")

        # Сначала сохраняем в JSON, чтобы получить ID
        recording_id = save_to_json(data)
        print(f"✅ Запись сохранена в JSON с ID: {recording_id}")

        # Добавляем ID в данные для RDF
        data_with_id = {**data, 'id': recording_id}

        # Добавляем запись в RDF граф
        rec_id = manager.add_recording(data_with_id)
        print(f"✅ Запись добавлена в RDF граф")

        # Сохраняем граф
        manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
        print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

        print("=" * 60 + "\n")
        return jsonify({'status': 'success', 'id': recording_id})

    except Exception as e:
        print(f"❌ Ошибка при добавлении записи: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/recording/<recording_id>')
def api_get_recording(recording_id):
    print(f"🔍 Запрос детальной информации для ID: {recording_id}")
    try:
        recording = manager.get_recording_by_id(recording_id)
        if recording:
            print(f"✅ Найдена запись: {recording.get('title')}")
            print(f"   Исполнители: {recording.get('performers')}")
            return jsonify(recording)
        else:
            print(f"❌ Запись не найдена: {recording_id}")
            return jsonify({'error': 'Запись не найдена'}), 404
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/update_recording/<recording_id>', methods=['POST'])
def api_update_recording(recording_id):
    """API для обновления записи"""
    try:
        data = request.json
        print(f"📝 Обновление записи {recording_id}:")
        print(f"   Title: {data.get('title')}")
        print(f"   Genre: {data.get('genre')}")
        print(f"   Location: {data.get('location')}")
        print(f"   Collection: {data.get('collection')}")
        print(f"   Performers: {data.get('performers')}")

        # Обновляем в JSON
        save_to_json(data, recording_id)
        print(f"✅ Запись обновлена в JSON")

        # Обновляем в RDF графе
        success, message = manager.update_recording(recording_id, data)

        if success:
            # Сохраняем граф
            manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
            print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")
            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message}), 400

    except Exception as e:
        print(f"❌ Ошибка обновления: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/delete_recording/<recording_id>', methods=['DELETE'])
def api_delete_recording(recording_id):
    """API для удаления записи"""
    try:
        print(f"🗑️ Удаление записи {recording_id}")

        # Удаляем из JSON
        delete_from_json(recording_id)

        # Удаляем из RDF графа
        success, message = manager.delete_recording(recording_id)

        if success:
            # Сохраняем граф
            manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
            print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")
            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message}), 404

    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/export_mets')
def api_export_mets():
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(EXPORTS_DIR, f"mets_{timestamp}.xml")
        manager.export_to_mets(output_file)
        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True, download_name=f"mets_{timestamp}.xml")
        else:
            return jsonify({'status': 'error', 'message': 'Файл не создан'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/vocabulary/<category>')
def api_get_vocabulary(category):
    """API для получения элементов словаря"""
    items = manager.get_vocabulary_by_category(category)
    return jsonify(items)


@app.route('/api/add_to_vocabulary', methods=['POST'])
def api_add_to_vocabulary():
    """API для добавления элемента в словарь"""
    try:
        data = request.json
        category = data.get('category')
        name = data.get('name')

        if not category or not name:
            return jsonify({'error': 'Не указана категория или название'}), 400

        # Проверяем допустимые категории
        valid_categories = ['ethnos', 'genres', 'locations', 'collections', 'instruments']
        if category not in valid_categories:
            return jsonify({'error': 'Недопустимая категория'}), 400

        item = manager.add_to_vocabulary(category, name)
        return jsonify({'status': 'success', 'item': item})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/debug/recordings')
def debug_recordings():
    """Отладка - показать все записи"""
    recordings = manager.get_all_recordings()
    return jsonify(recordings)


if __name__ == '__main__':
    print(f"🚀 Запуск сервера...")
    print(f"🌐 http://localhost:5000")
    app.run(debug=True, port=5000)