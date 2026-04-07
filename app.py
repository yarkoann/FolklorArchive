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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ONTOLOGY_PATH = os.path.join(BASE_DIR, "ontology", "folklor_ontology.owl")
DATA_PATH = os.path.join(BASE_DIR, "data", "recordings.json")
VOCAB_PATH = os.path.join(BASE_DIR, "data", "controlled_vocabulary.json")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(EXPORTS_DIR, exist_ok=True)

manager = FolklorMetadataManager(ontology_path=ONTOLOGY_PATH)


def load_vocabulary():
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
    if not os.path.exists(DATA_PATH):
        ensure_json_exists()
        return

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

            performers = rec.get('performers', [])
            if isinstance(performers, str):
                performers = [{'name': performers, 'ethnos': rec.get('ethnos', '')}]

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

            manager.add_recording(recording_data)
            print(f"   ✅ Запись добавлена в RDF")
            count += 1

        print(f"\n✅ Загружено {count} записей из JSON в RDF граф")

        manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
        print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        traceback.print_exc()


def save_to_json(recording_data, recording_id=None):
    json_path = DATA_PATH

    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            recordings = data.get('recordings', [])
    else:
        data = {'version': '1.0', 'recordings': []}
        recordings = []

    if not recording_id:
        recording_id = f"rec_{uuid.uuid4().hex[:8]}"

    existing_index = None
    for i, rec in enumerate(recordings):
        if rec.get('id') == recording_id:
            existing_index = i
            break

    new_recording = {
        'id': recording_id,
        'title': recording_data.get('title', ''),
        'inventory_number': recording_data.get('inventory_number', ''),
        'recording_date': recording_data.get('recording_date', '') or recording_data.get('date', ''),
        'duration': recording_data.get('duration', ''),
        'performers': recording_data.get('performers', []),
        'genre': recording_data.get('genre', ''),
        'ethical_status': recording_data.get('ethical_status', '') or recording_data.get('status', 'публичный_доступ'),
        'location': recording_data.get('location', ''),
        'collection': recording_data.get('collection', ''),
        'local_terms': recording_data.get('local_terms', []),
        'description': recording_data.get('description', ''),
        'updated_at': datetime.now().isoformat()
    }

    if existing_index is None:
        new_recording['created_at'] = datetime.now().isoformat()
        recordings.append(new_recording)
        print(f"✅ Добавлена новая запись в JSON: {recording_id}")
    else:
        if 'created_at' in recordings[existing_index]:
            new_recording['created_at'] = recordings[existing_index]['created_at']
        recordings[existing_index] = new_recording
        print(f"✅ Обновлена запись в JSON: {recording_id}")

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
    if request.args.get('performance_form'):
        filters['performance_form'] = request.args.get('performance_form')
    if request.args.get('q'):
        filters['search'] = request.args.get('q')

    page = int(request.args.get('page', 1))
    sort = request.args.get('sort', 'title')

    results = manager.facet_search(filters=filters, page=page, sort=sort)
    return jsonify(results)


@app.route('/api/facets')
def api_facets():
    facets = manager.get_facet_counts()
    return jsonify(facets)


@app.route('/api/add_recording', methods=['POST'])
def api_add_recording():
    try:
        data = request.json
        print("\n" + "=" * 60)
        print("📥 ПОЛУЧЕНЫ ДАННЫЕ ДЛЯ ДОБАВЛЕНИЯ:")
        print("=" * 60)
        print(f"Title: {data.get('title')}")
        print(f"Performers: {data.get('performers')}")

        recording_id = save_to_json(data)
        print(f"✅ Запись сохранена в JSON с ID: {recording_id}")

        data_with_id = {**data, 'id': recording_id}
        rec_id = manager.add_recording(data_with_id)
        print(f"✅ Запись добавлена в RDF граф")

        manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
        print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

        print("=" * 60 + "\n")
        return jsonify({'status': 'success', 'id': recording_id})

    except Exception as e:
        print(f"❌ Ошибка при добавлении записи: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 400


@app.route('/api/recording/<recording_id>', methods=['GET'])
def api_get_recording(recording_id):
    """API для получения детальной информации о записи"""
    print(f"🔍 Запрос детальной информации для ID: {recording_id}")
    try:
        # Пробуем получить из JSON
        if os.path.exists(DATA_PATH):
            with open(DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for rec in data.get('recordings', []):
                    if rec.get('id') == recording_id:
                        print(f"✅ Найдена запись в JSON: {rec.get('title')}")
                        # Приводим к единому формату
                        formatted_rec = {
                            'id': rec.get('id'),
                            'title': rec.get('title', ''),
                            'inventory_number': rec.get('inventory_number', ''),
                            'date': rec.get('recording_date', '') or rec.get('date', ''),
                            'duration': rec.get('duration', ''),
                            'status': rec.get('ethical_status', '') or rec.get('status', ''),
                            'genre': rec.get('genre', ''),
                            'location': rec.get('location', ''),
                            'collection': rec.get('collection', ''),
                            'description': rec.get('description', ''),
                            'local_terms': rec.get('local_terms', []),
                            'performers': rec.get('performers', []),
                            'created_at': rec.get('created_at', ''),
                            'updated_at': rec.get('updated_at', '')
                        }

                        # Если нет performers, но есть старые поля
                        if not formatted_rec['performers'] and rec.get('performer'):
                            formatted_rec['performers'] = [{
                                'name': rec.get('performer', ''),
                                'ethnos': rec.get('ethnos', ''),
                                'performance_form': rec.get('performance_form', ''),
                                'instruments': rec.get('instruments', [])
                            }]

                        return jsonify(formatted_rec)

        # Если не нашли в JSON, пробуем из RDF
        recording = manager.get_recording_by_id(recording_id)
        if recording:
            print(f"✅ Найдена запись в RDF: {recording.get('title')}")
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
    try:
        data = request.json
        print(f"📝 Обновление записи {recording_id}:")
        print(f"   Title: {data.get('title')}")
        print(f"   Performers: {data.get('performers')}")

        save_to_json(data, recording_id)
        print(f"✅ Запись обновлена в JSON")

        success, message = manager.update_recording(recording_id, data)

        if success:
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
    try:
        print(f"🗑️ Удаление записи {recording_id}")

        delete_from_json(recording_id)
        success, message = manager.delete_recording(recording_id)

        if success:
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
    items = manager.get_vocabulary_by_category(category)
    return jsonify(items)


@app.route('/api/add_to_vocabulary', methods=['POST'])
def api_add_to_vocabulary():
    try:
        data = request.json
        category = data.get('category')
        name = data.get('name')

        if not category or not name:
            return jsonify({'error': 'Не указана категория или название'}), 400

        valid_categories = ['ethnos', 'genres', 'locations', 'collections', 'instruments']
        if category not in valid_categories:
            return jsonify({'error': 'Недопустимая категория'}), 400

        item = manager.add_to_vocabulary(category, name)
        return jsonify({'status': 'success', 'item': item})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/debug/recordings')
def debug_recordings():
    recordings = manager.get_all_recordings()
    return jsonify(recordings)


if __name__ == '__main__':
    print(f"🚀 Запуск сервера...")
    print(f"🌐 http://localhost:5000")
    app.run(debug=True, port=5000)