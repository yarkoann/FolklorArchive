from flask import Flask, render_template, request, jsonify, send_file
from src.metadata_manager import FolklorMetadataManager
from datetime import datetime
import json
import os
import csv
import traceback
from rdflib.namespace import RDF, RDFS

app = Flask(__name__)

# Определяем пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ONTOLOGY_PATH = os.path.join(BASE_DIR, "ontology", "folklor_ontology.owl")
DATA_PATH = os.path.join(BASE_DIR, "data", "recordings.csv")
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


def ensure_csv_exists():
    """Создание CSV файла если его нет"""
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'title', 'inventory_number', 'recording_date', 'duration',
                             'performer', 'ethnos', 'genre', 'ethical_status', 'location',
                             'collection', 'local_terms', 'description'])
        print(f"✅ Создан новый CSV файл: {DATA_PATH}")


def load_existing_data():
    """Загрузка существующих данных из CSV без перезаписи"""
    if not os.path.exists(DATA_PATH):
        ensure_csv_exists()
        return

    # Проверяем, есть ли уже записи в графе
    existing = manager.get_all_recordings()
    if existing:
        print(f"📊 В графе уже есть {len(existing)} записей, пропускаем загрузку из CSV")
        return

    print(f"\n{'=' * 60}")
    print(f"📂 ЗАГРУЗКА ДАННЫХ ИЗ CSV")
    print(f"{'=' * 60}")

    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"Найдено строк в CSV: {len(rows)}")

            count = 0
            for row in rows:
                if not row.get('title'):
                    continue

                print(f"\n📄 Загрузка: {row.get('title')}")

                # Обработка множественных исполнителей
                performers = []
                performer_field = row.get('performer', '')
                ethnos_field = row.get('ethnos', '')

                if ';' in performer_field:
                    # Несколько исполнителей
                    performer_names = performer_field.split(';')
                    performer_ethnos = ethnos_field.split(';') if ';' in ethnos_field else [''] * len(performer_names)

                    for i in range(len(performer_names)):
                        if performer_names[i].strip():
                            performers.append({
                                'name': performer_names[i].strip(),
                                'ethnos': performer_ethnos[i].strip() if i < len(performer_ethnos) else ''
                            })
                else:
                    # Один исполнитель
                    if performer_field.strip():
                        performers.append({
                            'name': performer_field.strip(),
                            'ethnos': ethnos_field.strip() if ethnos_field else ''
                        })

                print(f"   Исполнители: {performers}")

                # Обработка местных терминов
                local_terms = []
                if 'local_terms' in row and row['local_terms']:
                    terms_str = row['local_terms'].strip('"')
                    local_terms = [t.strip() for t in terms_str.split(',') if t.strip()]
                    print(f"   Местные термины: {local_terms}")

                recording_data = {
                    'title': row['title'],
                    'inventory_number': row.get('inventory_number', ''),
                    'recording_date': row.get('recording_date', ''),
                    'duration': row.get('duration', ''),
                    'performers': performers,
                    'genre': row.get('genre', ''),
                    'ethical_status': row.get('ethical_status', ''),
                    'location': row.get('location', ''),
                    'collection': row.get('collection', ''),
                    'local_terms': local_terms,
                    'description': row.get('description', '')
                }

                rec_id = manager.add_recording(recording_data)
                print(f"   ✅ Запись добавлена с ID: {rec_id}")
                count += 1

            print(f"\n✅ Загружено {count} записей из CSV")

            # Сохраняем граф после загрузки
            manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
            print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

    except Exception as e:
        print(f"❌ Ошибка при загрузке: {e}")
        traceback.print_exc()


def save_to_csv(recording_data):
    """Сохранение новой записи в CSV файл"""
    csv_path = os.path.join(BASE_DIR, "data", "recordings.csv")

    # Определяем новый ID
    import csv
    max_id = 0
    rows = []

    # Читаем существующие записи
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            for row in rows:
                try:
                    max_id = max(max_id, int(row.get('id', 0)))
                except:
                    pass

    # Создаем новую запись
    new_id = max_id + 1

    # Форматирование исполнителей (поддержка множественных)
    performers_str = ''
    ethnos_str = ''
    performers = recording_data.get('performers', [])

    if performers and len(performers) > 0:
        performer_names = []
        performer_ethnos = []
        for p in performers:
            if p.get('name') and p['name'].strip():
                performer_names.append(p['name'].strip())
                performer_ethnos.append(p.get('ethnos', '').strip() if p.get('ethnos') else '')
        performers_str = ';'.join(performer_names)
        ethnos_str = ';'.join(performer_ethnos)
        print(f"📝 Сохранение исполнителей в CSV: {performers_str} / {ethnos_str}")

    # Форматирование местных терминов
    local_terms = recording_data.get('local_terms', '')
    if isinstance(local_terms, list):
        local_terms_str = ','.join([t.strip() for t in local_terms if t.strip()])
    else:
        local_terms_str = str(local_terms) if local_terms else ''

    new_row = {
        'id': str(new_id),
        'title': recording_data.get('title', ''),
        'inventory_number': recording_data.get('inventory_number', ''),
        'recording_date': recording_data.get('recording_date', ''),
        'duration': recording_data.get('duration', ''),
        'performer': performers_str,
        'ethnos': ethnos_str,
        'genre': recording_data.get('genre', ''),
        'ethical_status': recording_data.get('ethical_status', ''),
        'location': recording_data.get('location', ''),
        'collection': recording_data.get('collection', ''),
        'local_terms': local_terms_str,
        'description': recording_data.get('description', '')
    }

    rows.append(new_row)

    # Сохраняем обратно в CSV
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['id', 'title', 'inventory_number', 'recording_date', 'duration',
                      'performer', 'ethnos', 'genre', 'ethical_status', 'location',
                      'collection', 'local_terms', 'description']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ CSV сохранен. Всего записей: {len(rows)}")
    return new_id


# Загружаем существующие данные
ensure_csv_exists()
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

        # Добавляем запись в граф
        rec_id = manager.add_recording(data)
        print(f"\n✅ Запись добавлена в граф с ID: {rec_id}")

        # Сохраняем граф
        manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
        print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

        # Сохраняем в CSV
        try:
            csv_id = save_to_csv(data)
            print(f"✅ Запись сохранена в CSV с ID: {csv_id}")
        except Exception as csv_error:
            print(f"⚠️ Ошибка при сохранении в CSV: {csv_error}")
            traceback.print_exc()

        print("=" * 60 + "\n")
        return jsonify({'status': 'success', 'id': rec_id})

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

        success, message = manager.update_recording(recording_id, data)

        if success:
            # Сохраняем граф
            manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
            print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

            # Обновляем запись в CSV
            update_result = update_in_csv(recording_id, data)
            if update_result:
                print(f"✅ Запись обновлена в CSV")
            else:
                print(f"⚠️ Запись не найдена в CSV")

            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message}), 400

    except Exception as e:
        print(f"❌ Ошибка обновления: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def update_in_csv(recording_id, recording_data):
    """Обновление записи в CSV файле"""
    csv_path = os.path.join(BASE_DIR, "data", "recordings.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ CSV файл не найден: {csv_path}")
        return False

    rows = []
    updated = False

    # Читаем все строки
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Находим и обновляем нужную строку
    clean_id = recording_id.replace('rec_', '')
    print(f"🔍 Поиск записи с ID {clean_id} в CSV")

    for row in rows:
        if row.get('id') == clean_id:
            print(f"✅ Найдена запись в CSV: {row.get('title')}")

            # Форматируем исполнителей для CSV
            performers_str = ''
            ethnos_str = ''
            if recording_data.get('performers'):
                performer_list = []
                ethnos_list = []
                for p in recording_data['performers']:
                    if p.get('name') and p['name'].strip():
                        performer_list.append(p['name'].strip())
                        ethnos_list.append(p.get('ethnos', '').strip() if p.get('ethnos') else '')
                performers_str = ';'.join(performer_list)
                ethnos_str = ';'.join(ethnos_list)
                print(f"📝 Исполнители для CSV: {performers_str}")
                print(f"📝 Этносы для CSV: {ethnos_str}")

            # Форматируем местные термины
            local_terms_str = ''
            if recording_data.get('local_terms'):
                if isinstance(recording_data['local_terms'], list):
                    local_terms_str = ','.join([t.strip() for t in recording_data['local_terms'] if t.strip()])
                else:
                    local_terms_str = recording_data['local_terms']

            # Обновляем поля
            row['title'] = recording_data.get('title', '')
            row['inventory_number'] = recording_data.get('inventory_number', '')
            row['recording_date'] = recording_data.get('recording_date', '')
            row['duration'] = recording_data.get('duration', '')
            row['performer'] = performers_str
            row['ethnos'] = ethnos_str
            row['genre'] = recording_data.get('genre', '')
            row['ethical_status'] = recording_data.get('ethical_status', '')
            row['location'] = recording_data.get('location', '')
            row['collection'] = recording_data.get('collection', '')
            row['local_terms'] = local_terms_str
            row['description'] = recording_data.get('description', '')

            print(f"📝 Обновление строки {clean_id} в CSV:")
            print(f"   Title: {row['title']}")
            print(f"   Performer: '{performers_str}'")
            print(f"   Ethnos: '{ethnos_str}'")

            updated = True
            break

    if updated:
        # Сохраняем обратно в CSV
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Запись {recording_id} обновлена в CSV")
        return True
    else:
        print(f"⚠️ Запись {recording_id} не найдена в CSV")
        return False


@app.route('/api/delete_recording/<recording_id>', methods=['DELETE'])
def api_delete_recording(recording_id):
    """API для удаления записи"""
    try:
        print(f"🗑️ Удаление записи {recording_id}")

        # Удаляем из графа
        success, message = manager.delete_recording(recording_id)

        if success:
            # Сохраняем граф
            manager.g.serialize(destination=ONTOLOGY_PATH, format="xml")
            print(f"✅ Граф сохранен в {ONTOLOGY_PATH}")

            # Удаляем из CSV
            delete_result = delete_from_csv(recording_id)
            if delete_result:
                print(f"✅ Запись удалена из CSV")
            else:
                print(f"⚠️ Запись не найдена в CSV")

            return jsonify({'status': 'success', 'message': message})
        else:
            return jsonify({'status': 'error', 'message': message}), 404
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def delete_from_csv(recording_id):
    """Удаление записи из CSV файла"""
    csv_path = os.path.join(BASE_DIR, "data", "recordings.csv")

    if not os.path.exists(csv_path):
        print(f"⚠️ CSV файл не найден: {csv_path}")
        return False

    rows = []
    deleted = False
    clean_id = recording_id.replace('rec_', '')

    print(f"🔍 Поиск записи с ID {clean_id} в CSV для удаления")

    # Читаем все строки
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Фильтруем строки, оставляя все кроме удаляемой
    new_rows = []
    for row in rows:
        if row.get('id') == clean_id:
            print(f"✅ Найдена запись для удаления: {row.get('title')}")
            deleted = True
            # Не добавляем эту строку в new_rows
        else:
            new_rows.append(row)

    if deleted:
        # Сохраняем обратно в CSV (без удаленной строки)
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_rows)
        print(f"✅ Запись {recording_id} удалена из CSV")
        return True
    else:
        print(f"⚠️ Запись {recording_id} не найдена в CSV")
        return False


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