from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
import json
from datetime import datetime
import uuid
import os
import traceback
import re


class FolklorMetadataManager:
    def __init__(self, ontology_path="ontology/folklor_ontology.owl"):
        """Инициализация менеджера метаданных"""
        print(f"🔄 Инициализация FolklorMetadataManager...")
        print(f"📁 Путь к онтологии: {ontology_path}")

        self.g = Graph()
        self.FOLK = Namespace("http://agiki.ru/folklor#")

        try:
            # Проверяем существование файла
            if not os.path.exists(ontology_path):
                print(f"⚠️ Файл онтологии не найден: {ontology_path}")
                # Создаем базовую онтологию
                self._create_basic_ontology()
            else:
                print(f"📂 Загрузка онтологии из {ontology_path}")
                self.g.parse(ontology_path, format="xml")
                print(f"✅ Онтология загружена. Триплетов: {len(self.g)}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке онтологии: {e}")
            traceback.print_exc()
            # Создаем базовую онтологию при ошибке
            self._create_basic_ontology()

        # Загружаем контролируемый словарь
        vocab_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "data", "controlled_vocabulary.json")
        print(f"📁 Путь к словарю: {vocab_path}")

        try:
            with open(vocab_path, "r", encoding="utf-8") as f:
                self.vocabulary = json.load(f)
            print(f"✅ Словарь загружен. Этносов: {len(self.vocabulary['ethnos'])}")
        except Exception as e:
            print(f"⚠️ Ошибка при загрузке словаря: {e}")
            # Создаем пустой словарь
            self.vocabulary = {
                'ethnos': [],
                'genres': [],
                'locations': [],
                'collections': [],
                'instruments': []
            }

    def _create_basic_ontology(self):
        """Создание базовой онтологии если файл не найден"""
        print("🔄 Создание базовой онтологии...")

        # Базовые классы
        classes = [
            "АудиоЗапись", "Исполнитель", "Этнос", "Жанр",
            "ОбрядовыйСтатус", "Локация", "Инструмент", "Коллекция"
        ]

        for class_name in classes:
            self.g.add((self.FOLK[class_name], RDF.type, OWL.Class))
            self.g.add((self.FOLK[class_name], RDFS.label, Literal(class_name, lang="ru")))

        # Этические флаги
        ethical_flags = ["публичный_доступ", "ограниченный_доступ", "требует_согласия_общины"]
        for flag in ethical_flags:
            self.g.add((self.FOLK[flag], RDF.type, self.FOLK["ЭтическийСтатус"]))
            self.g.add((self.FOLK[flag], RDFS.label, Literal(flag, lang="ru")))

        print(f"✅ Базовая онтология создана. Триплетов: {len(self.g)}")

    def add_recording(self, recording_data):
        """Добавление новой записи в архив"""
        recording_id = f"rec_{uuid.uuid4().hex[:8]}"
        recording = URIRef(self.FOLK[recording_id])

        print(f"\n➕ Добавление записи {recording_id}")

        # Базовые метаданные
        self.g.add((recording, RDF.type, self.FOLK["АудиоЗапись"]))
        self.g.add((recording, self.FOLK["название"], Literal(recording_data["title"], lang="ru")))

        # Инвентарный номер
        if recording_data.get("inventory_number"):
            self.g.add((recording, self.FOLK["инвентарныйНомер"], Literal(recording_data["inventory_number"])))

        # Дата записи
        if recording_data.get("recording_date"):
            try:
                date_str = recording_data["recording_date"].split('T')[0].split(' ')[0]
                self.g.add((recording, self.FOLK["датаЗаписи"], Literal(date_str, datatype=XSD.date)))
            except Exception as e:
                print(f"   ⚠️ Ошибка даты: {e}")

        # Длительность
        if recording_data.get("duration"):
            self.g.add((recording, self.FOLK["длительность"], Literal(str(recording_data["duration"]))))

        # Исполнители
        performers = recording_data.get('performers', [])
        print(f"   👥 Исполнителей: {len(performers)}")
        for i, performer in enumerate(performers):
            if performer.get('name'):
                performer_uri = self._get_or_create_performer(performer)
                if performer_uri:
                    self.g.add((recording, self.FOLK["имеетИсполнителя"], performer_uri))
                    print(f"      ✅ Исполнитель {i + 1}: {performer['name']} - {performer.get('ethnos', '')}")

        # Жанр
        if recording_data.get("genre") and recording_data["genre"] != "new" and recording_data["genre"] != "":
            genre_uri = self._get_or_create_genre(recording_data["genre"])
            if genre_uri:
                self.g.add((recording, self.FOLK["имеетЖанр"], genre_uri))
                # Добавляем метку для жанра, если её нет
                if not list(self.g.triples((genre_uri, RDFS.label, None))):
                    self.g.add((genre_uri, RDFS.label, Literal(recording_data["genre"], lang="ru")))

        # Этический статус
        if recording_data.get("ethical_status"):
            status_uri = self.FOLK[recording_data["ethical_status"]]
            self.g.add((recording, self.FOLK["этическийСтатус"], status_uri))

        # Локация
        if recording_data.get("location") and recording_data["location"] != "new" and recording_data["location"] != "":
            location_uri = self._get_or_create_location(recording_data["location"])
            if location_uri:
                self.g.add((recording, self.FOLK["записанаВЛокации"], location_uri))
                # Добавляем метку для локации, если её нет
                if not list(self.g.triples((location_uri, RDFS.label, None))):
                    self.g.add((location_uri, RDFS.label, Literal(recording_data["location"], lang="ru")))

        # Коллекция
        if recording_data.get("collection") and recording_data["collection"] != "new" and recording_data[
            "collection"] != "":
            collection_uri = self._get_or_create_collection(recording_data["collection"])
            if collection_uri:
                self.g.add((recording, self.FOLK["входитВКоллекцию"], collection_uri))
                # Добавляем метку для коллекции, если её нет
                if not list(self.g.triples((collection_uri, RDFS.label, None))):
                    self.g.add((collection_uri, RDFS.label, Literal(recording_data["collection"], lang="ru")))

        # Местные термины
        local_terms = recording_data.get('local_terms', [])
        if isinstance(local_terms, str):
            local_terms = [t.strip() for t in local_terms.split(',') if t.strip()]
        for term in local_terms:
            if term:
                self.g.add((recording, self.FOLK["местныеТермины"], Literal(term, lang="ru")))

        # Описание
        if recording_data.get("description"):
            self.g.add((recording, self.FOLK["описание"], Literal(recording_data["description"], lang="ru")))

        print(f"✅ Запись {recording_id} добавлена")
        return recording_id

    def _get_or_create_performer(self, performer_data):
        """Создание исполнителя"""
        name = performer_data.get('name')
        if not name:
            return None

        # Используем UUID для гарантии уникальности
        performer_id = f"perf_{uuid.uuid4().hex[:8]}"
        performer_uri = self.FOLK[performer_id]

        # Создаем нового исполнителя
        self.g.add((performer_uri, RDF.type, self.FOLK["Исполнитель"]))
        self.g.add((performer_uri, self.FOLK["имя"], Literal(name, lang="ru")))

        # Этнос
        ethnos = performer_data.get('ethnos')
        if ethnos and ethnos != "new" and ethnos != "":
            ethnos_uri = self._get_or_create_ethnos(ethnos)
            if ethnos_uri:
                self.g.add((performer_uri, self.FOLK["принадлежитКЭтносу"], ethnos_uri))
                # Добавляем метку для этноса, если её нет
                if not list(self.g.triples((ethnos_uri, RDFS.label, None))):
                    self.g.add((ethnos_uri, RDFS.label, Literal(ethnos, lang="ru")))

        return performer_uri

    def _get_or_create_ethnos(self, ethnos_name):
        """Создание этноса"""
        if not ethnos_name or ethnos_name == "new":
            return None

        # Ищем существующий этнос по метке
        for s, p, o in self.g.triples((None, RDFS.label, Literal(ethnos_name, lang="ru"))):
            if (s, RDF.type, self.FOLK["Этнос"]) in self.g:
                return s

        # Если не нашли, создаем новый
        safe_name = ethnos_name.lower().replace(' ', '_')
        ethnos_uri = self.FOLK[f"ethnos_{safe_name}"]

        if (ethnos_uri, RDF.type, self.FOLK["Этнос"]) not in self.g:
            self.g.add((ethnos_uri, RDF.type, self.FOLK["Этнос"]))
            self.g.add((ethnos_uri, RDFS.label, Literal(ethnos_name, lang="ru")))

        return ethnos_uri

    def _get_or_create_genre(self, genre_name):
        """Создание жанра"""
        if not genre_name or genre_name == "new":
            return None

        # Ищем существующий жанр по метке
        for s, p, o in self.g.triples((None, RDFS.label, Literal(genre_name, lang="ru"))):
            if (s, RDF.type, self.FOLK["Жанр"]) in self.g:
                return s

        # Если не нашли, создаем новый
        safe_name = genre_name.lower().replace(' ', '_')
        genre_uri = self.FOLK[f"genre_{safe_name}"]

        if (genre_uri, RDF.type, self.FOLK["Жанр"]) not in self.g:
            self.g.add((genre_uri, RDF.type, self.FOLK["Жанр"]))
            self.g.add((genre_uri, RDFS.label, Literal(genre_name, lang="ru")))

        return genre_uri

    def _get_or_create_location(self, location_name):
        """Создание локации"""
        if not location_name or location_name == "new":
            return None

        # Ищем существующую локацию по метке
        for s, p, o in self.g.triples((None, RDFS.label, Literal(location_name, lang="ru"))):
            if (s, RDF.type, self.FOLK["Локация"]) in self.g:
                return s

        # Если не нашли, создаем новую
        safe_name = location_name.lower().replace(' ', '_')
        loc_uri = self.FOLK[f"loc_{safe_name}"]

        if (loc_uri, RDF.type, self.FOLK["Локация"]) not in self.g:
            self.g.add((loc_uri, RDF.type, self.FOLK["Локация"]))
            self.g.add((loc_uri, RDFS.label, Literal(location_name, lang="ru")))

        return loc_uri

    def _get_or_create_collection(self, collection_name):
        """Создание коллекции"""
        if not collection_name or collection_name == "new":
            return None

        # Ищем существующую коллекцию по метке
        for s, p, o in self.g.triples((None, RDFS.label, Literal(collection_name, lang="ru"))):
            if (s, RDF.type, self.FOLK["Коллекция"]) in self.g:
                return s

        # Если не нашли, создаем новую
        safe_name = collection_name.lower().replace(' ', '_').replace('№', '').replace('(', '').replace(')', '')
        coll_uri = self.FOLK[f"coll_{safe_name}"]

        if (coll_uri, RDF.type, self.FOLK["Коллекция"]) not in self.g:
            self.g.add((coll_uri, RDF.type, self.FOLK["Коллекция"]))
            self.g.add((coll_uri, RDFS.label, Literal(collection_name, lang="ru")))

        return coll_uri

    def get_all_recordings(self):
        """Получение всех записей из графа"""
        try:
            results = []

            print("🔍 Поиск всех записей в графе...")

            # Находим все записи
            for s, p, o in self.g.triples((None, RDF.type, self.FOLK["АудиоЗапись"])):
                recording_uri = s
                print(f"   Найдена запись: {recording_uri}")

                # Извлекаем ID
                recording_str = str(recording_uri)
                if '#' in recording_str:
                    recording_id = recording_str.split('#')[-1]
                else:
                    recording_id = recording_str.split('/')[-1]

                # Базовая структура записи
                recording_data = {
                    'id': recording_id,
                    'recording': recording_str,
                    'title': '',
                    'date': '',
                    'duration': '',
                    'status': '',
                    'genre': '',
                    'performers': [],
                    'inventory_number': '',
                    'description': '',
                    'location': '',
                    'collection': '',
                    'local_terms': []
                }

                # Собираем все свойства записи
                for s2, p2, o2 in self.g.triples((recording_uri, None, None)):
                    if p2 == self.FOLK["название"]:
                        recording_data['title'] = str(o2)
                    elif p2 == self.FOLK["инвентарныйНомер"]:
                        recording_data['inventory_number'] = str(o2)
                    elif p2 == self.FOLK["датаЗаписи"]:
                        date_str = str(o2).split('T')[0] if 'T' in str(o2) else str(o2)
                        recording_data['date'] = date_str
                    elif p2 == self.FOLK["длительность"]:
                        recording_data['duration'] = str(o2)
                    elif p2 == self.FOLK["этическийСтатус"]:
                        status_str = str(o2).split('#')[-1]
                        recording_data['status'] = status_str
                    elif p2 == self.FOLK["описание"]:
                        recording_data['description'] = str(o2)
                    elif p2 == self.FOLK["местныеТермины"]:
                        recording_data['local_terms'].append(str(o2))
                    elif p2 == self.FOLK["имеетЖанр"]:
                        # Получаем название жанра по метке
                        for s3, p3, o3 in self.g.triples((o2, RDFS.label, None)):
                            recording_data['genre'] = str(o3)
                            break
                    elif p2 == self.FOLK["записанаВЛокации"]:
                        # Получаем название локации по метке
                        for s3, p3, o3 in self.g.triples((o2, RDFS.label, None)):
                            recording_data['location'] = str(o3)
                            break
                    elif p2 == self.FOLK["входитВКоллекцию"]:
                        # Получаем название коллекции по метке
                        for s3, p3, o3 in self.g.triples((o2, RDFS.label, None)):
                            recording_data['collection'] = str(o3)
                            break
                    elif p2 == self.FOLK["имеетИсполнителя"]:
                        performer_info = {'name': '', 'ethnos': ''}

                        # Ищем имя исполнителя
                        for s3, p3, o3 in self.g.triples((o2, self.FOLK["имя"], None)):
                            performer_info['name'] = str(o3)
                            break

                        # Ищем этнос исполнителя
                        for s3, p3, o3 in self.g.triples((o2, self.FOLK["принадлежитКЭтносу"], None)):
                            # Получаем название этноса по метке
                            for s4, p4, o4 in self.g.triples((o3, RDFS.label, None)):
                                performer_info['ethnos'] = str(o4)
                                break

                        if performer_info['name']:
                            recording_data['performers'].append(performer_info)

                results.append(recording_data)

            print(f"✅ Загружено {len(results)} записей из графа")
            return results

        except Exception as e:
            print(f"❌ Ошибка в get_all_recordings: {e}")
            traceback.print_exc()
            return []

    def get_facet_counts(self):
        """Получение статистики для фасетной навигации"""
        all_recordings = self.get_all_recordings()

        print(f"📊 Подсчет фасетов для {len(all_recordings)} записей")

        facets = {
            'ethnos': {},
            'genre': {},
            'status': {},
            'decades': {},
            'location': {},
            'collection': {}
        }

        for rec in all_recordings:
            # Этносы (из исполнителей)
            for performer in rec.get('performers', []):
                if performer.get('ethnos'):
                    ethnos = performer['ethnos']
                    facets['ethnos'][ethnos] = facets['ethnos'].get(ethnos, 0) + 1
                    print(f"      Добавлен этнос: {ethnos}")

            # Жанры
            if rec.get('genre'):
                genre = rec['genre']
                facets['genre'][genre] = facets['genre'].get(genre, 0) + 1

            # Статусы
            if rec.get('status'):
                status = rec['status']
                facets['status'][status] = facets['status'].get(status, 0) + 1

            # Локации
            if rec.get('location'):
                location = rec['location']
                facets['location'][location] = facets['location'].get(location, 0) + 1

            # Коллекции
            if rec.get('collection'):
                collection = rec['collection']
                facets['collection'][collection] = facets['collection'].get(collection, 0) + 1

            # Десятилетия
            if rec.get('date') and '-' in rec['date']:
                try:
                    year = int(rec['date'].split('-')[0])
                    decade = (year // 10) * 10
                    decade_key = f"{decade}-{decade + 9}"
                    facets['decades'][decade_key] = facets['decades'].get(decade_key, 0) + 1
                except:
                    pass

        print(f"📊 Фасеты: {facets}")
        return facets

    def facet_search(self, filters=None, page=1, per_page=10, sort="title"):
        """Фасетный поиск с фильтрацией и пагинацией"""
        if filters is None:
            filters = {}

        print(f"🔍 Поиск с фильтрами: {filters}")

        # Получаем все записи
        all_recordings = self.get_all_recordings()
        print(f"📊 Всего записей в базе: {len(all_recordings)}")

        # Фильтруем
        filtered_results = []
        for rec in all_recordings:
            match = True

            # Фильтр по этносу
            if filters.get('ethnos') and match:
                ethnos_found = False
                for performer in rec.get('performers', []):
                    if performer.get('ethnos', '').lower() == filters['ethnos'].lower():
                        ethnos_found = True
                        break
                if not ethnos_found:
                    match = False

            # Фильтр по жанру
            if filters.get('genre') and match:
                if rec.get('genre', '').lower() != filters['genre'].lower():
                    match = False

            # Фильтр по статусу
            if filters.get('status') and match:
                status_filter = filters['status'].replace('folk:', '').split('#')[-1]
                if status_filter not in rec.get('status', ''):
                    match = False

            # Фильтр по локации
            if filters.get('location') and match:
                if filters['location'].lower() != rec.get('location', '').lower():
                    match = False

            # Фильтр по коллекции
            if filters.get('collection') and match:
                if filters['collection'].lower() != rec.get('collection', '').lower():
                    match = False

            # Фильтр по десятилетию
            if filters.get('decade') and match:
                if rec.get('date') and '-' in rec['date']:
                    try:
                        year = int(rec['date'].split('-')[0])
                        decade_start = (year // 10) * 10
                        decade_end = decade_start + 9
                        decade_key = f"{decade_start}-{decade_end}"
                        if decade_key != filters['decade']:
                            match = False
                    except:
                        match = False
                else:
                    match = False

            # Фильтр по поисковому запросу
            if filters.get('search') and match:
                search_term = filters['search'].lower()
                title_match = search_term in rec.get('title', '').lower()

                # Поиск по исполнителям
                performer_match = False
                for p in rec.get('performers', []):
                    if search_term in p.get('name', '').lower():
                        performer_match = True
                        break

                # Поиск по описанию
                desc_match = search_term in rec.get('description', '').lower()

                if not (title_match or performer_match or desc_match):
                    match = False

            if match:
                filtered_results.append(rec)

        print(f"✅ После фильтрации: {len(filtered_results)} записей")

        # Сортировка
        if sort == "date_desc":
            filtered_results.sort(key=lambda x: x.get('date', ''), reverse=True)
        elif sort == "date_asc":
            filtered_results.sort(key=lambda x: x.get('date', ''))
        else:  # по названию
            filtered_results.sort(key=lambda x: x.get('title', '').lower())

        total = len(filtered_results)

        # Пагинация
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = filtered_results[start:end]

        return {
            'results': paginated_results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 1
        }

    def get_recording_by_id(self, recording_id):
        """Получение записи по ID"""
        all_recordings = self.get_all_recordings()
        for rec in all_recordings:
            if rec.get('id') == recording_id:
                return rec
        return None

    def update_recording(self, recording_id, recording_data):
        """Обновление существующей записи"""
        try:
            # Находим URI записи
            recording_uri = None
            for s, p, o in self.g.triples((None, RDF.type, self.FOLK["АудиоЗапись"])):
                if recording_id in str(s):
                    recording_uri = s
                    break

            if not recording_uri:
                return False, "Запись не найдена"

            print(f"📝 Обновление записи {recording_id} в графе")

            # Удаляем старые триплеты
            properties_to_remove = [
                self.FOLK["название"],
                self.FOLK["инвентарныйНомер"],
                self.FOLK["датаЗаписи"],
                self.FOLK["длительность"],
                self.FOLK["этическийСтатус"],
                self.FOLK["описание"],
                self.FOLK["имеетЖанр"],
                self.FOLK["записанаВЛокации"],
                self.FOLK["входитВКоллекцию"],
                self.FOLK["имеетИсполнителя"],
                self.FOLK["местныеТермины"],
            ]

            for prop in properties_to_remove:
                for triple in list(self.g.triples((recording_uri, prop, None))):
                    self.g.remove(triple)

            # Добавляем обновленные данные
            self.g.add((recording_uri, self.FOLK["название"], Literal(recording_data["title"], lang="ru")))

            if recording_data.get("inventory_number"):
                self.g.add((recording_uri, self.FOLK["инвентарныйНомер"], Literal(recording_data["inventory_number"])))

            if recording_data.get("recording_date"):
                try:
                    date_str = recording_data["recording_date"].split('T')[0].split(' ')[0]
                    self.g.add((recording_uri, self.FOLK["датаЗаписи"], Literal(date_str, datatype=XSD.date)))
                except Exception as e:
                    print(f"Ошибка парсинга даты: {e}")

            if recording_data.get("duration"):
                self.g.add((recording_uri, self.FOLK["длительность"], Literal(recording_data["duration"])))

            # Исполнители
            if recording_data.get("performers"):
                for performer in recording_data["performers"]:
                    if performer.get('name'):
                        performer_uri = self._get_or_create_performer(performer)
                        if performer_uri:
                            self.g.add((recording_uri, self.FOLK["имеетИсполнителя"], performer_uri))
                            print(
                                f"      Добавлен исполнитель: {performer.get('name')} - {performer.get('ethnos', '')}")

            # Жанр
            if recording_data.get("genre") and recording_data["genre"] != "new" and recording_data["genre"] != "":
                genre_uri = self._get_or_create_genre(recording_data["genre"])
                if genre_uri:
                    self.g.add((recording_uri, self.FOLK["имеетЖанр"], genre_uri))
                    # Добавляем метку для жанра, если её нет
                    if not list(self.g.triples((genre_uri, RDFS.label, None))):
                        self.g.add((genre_uri, RDFS.label, Literal(recording_data["genre"], lang="ru")))

            # Этический статус
            if recording_data.get("ethical_status"):
                status_uri = self.FOLK[recording_data["ethical_status"]]
                self.g.add((recording_uri, self.FOLK["этическийСтатус"], status_uri))

            # Локация
            if recording_data.get("location") and recording_data["location"] != "new" and recording_data[
                "location"] != "":
                location_uri = self._get_or_create_location(recording_data["location"])
                if location_uri:
                    self.g.add((recording_uri, self.FOLK["записанаВЛокации"], location_uri))
                    # Добавляем метку для локации, если её нет
                    if not list(self.g.triples((location_uri, RDFS.label, None))):
                        self.g.add((location_uri, RDFS.label, Literal(recording_data["location"], lang="ru")))

            # Коллекция
            if recording_data.get("collection") and recording_data["collection"] != "new" and recording_data[
                "collection"] != "":
                collection_uri = self._get_or_create_collection(recording_data["collection"])
                if collection_uri:
                    self.g.add((recording_uri, self.FOLK["входитВКоллекцию"], collection_uri))
                    # Добавляем метку для коллекции, если её нет
                    if not list(self.g.triples((collection_uri, RDFS.label, None))):
                        self.g.add((collection_uri, RDFS.label, Literal(recording_data["collection"], lang="ru")))

            # Местные термины
            if recording_data.get("local_terms"):
                terms = recording_data["local_terms"]
                if isinstance(terms, str):
                    terms = [t.strip() for t in terms.split(',') if t.strip()]
                for term in terms:
                    if term:
                        self.g.add((recording_uri, self.FOLK["местныеТермины"], Literal(term, lang="ru")))

            # Описание
            if recording_data.get("description"):
                self.g.add((recording_uri, self.FOLK["описание"], Literal(recording_data["description"], lang="ru")))

            return True, "Запись успешно обновлена"

        except Exception as e:
            print(f"❌ Ошибка при обновлении: {e}")
            traceback.print_exc()
            return False, str(e)

    def delete_recording(self, recording_id):
        """Удаление записи"""
        try:
            # Находим URI записи
            recording_uri = None
            for s, p, o in self.g.triples((None, RDF.type, self.FOLK["АудиоЗапись"])):
                if recording_id in str(s):
                    recording_uri = s
                    break

            if not recording_uri:
                return False, "Запись не найдена"

            # Удаляем все триплеты, связанные с записью
            for triple in list(self.g.triples((recording_uri, None, None))):
                self.g.remove(triple)

            return True, "Запись успешно удалена"

        except Exception as e:
            return False, str(e)

    def export_to_mets(self, output_file="exports/mets.xml"):
        """Экспорт метаданных в формате METS/ALTO"""
        try:
            import xml.etree.ElementTree as ET
            import xml.dom.minidom as minidom
        except ImportError:
            print("Ошибка: не удалось импортировать xml модули")
            return None

        # Создаем директорию для экспорта
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Создаем корневой элемент
        mets = ET.Element("mets")
        mets.set("xmlns", "http://www.loc.gov/METS/")
        mets.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        mets.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
        mets.set("xsi:schemaLocation",
                 "http://www.loc.gov/METS/ http://www.loc.gov/standards/mets/version191/mets.xsd")

        # METS Header
        metsHdr = ET.SubElement(mets, "metsHdr")
        metsHdr.set("CREATEDATE", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

        agent = ET.SubElement(metsHdr, "agent")
        agent.set("ROLE", "CREATOR")
        agent.set("TYPE", "ORGANIZATION")
        agent.text = "АГИКИ Фонограммархив"

        # Descriptive Metadata
        dmdSec = ET.SubElement(mets, "dmdSec")
        dmdSec.set("ID", "DMD1")

        mdWrap = ET.SubElement(dmdSec, "mdWrap")
        mdWrap.set("MDTYPE", "DC")

        xmlData = ET.SubElement(mdWrap, "xmlData")

        # Получаем все записи
        recordings = self.get_all_recordings()

        records = ET.SubElement(xmlData, "records")

        for rec in recordings:
            record = ET.SubElement(records, "record")

            if rec['title']:
                title_elem = ET.SubElement(record, "title")
                title_elem.text = rec['title']

            if rec['inventory_number']:
                inv_elem = ET.SubElement(record, "identifier")
                inv_elem.set("type", "inventory_number")
                inv_elem.text = rec['inventory_number']

            if rec['date']:
                date_elem = ET.SubElement(record, "date")
                date_elem.text = rec['date']

            # Исполнители
            for performer in rec.get('performers', []):
                if performer.get('name'):
                    creator_elem = ET.SubElement(record, "creator")
                    creator_text = performer['name']
                    if performer.get('ethnos'):
                        creator_text += f" ({performer['ethnos']})"
                    creator_elem.text = creator_text

            if rec.get('genre'):
                type_elem = ET.SubElement(record, "type")
                type_elem.text = rec['genre']

            if rec.get('description'):
                desc_elem = ET.SubElement(record, "description")
                desc_elem.text = rec['description']

            if rec.get('status'):
                rights_elem = ET.SubElement(record, "rights")
                rights_elem.text = rec['status']

        # Сохраняем с форматированием
        xml_str = ET.tostring(mets, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')

        with open(output_file, 'wb') as f:
            f.write(pretty_xml)

        print(f"✅ Метаданные экспортированы в {output_file}")
        return output_file

    def get_vocabulary(self):
        """Получение контролируемого словаря"""
        return self.vocabulary

    def get_vocabulary_by_category(self, category):
        """Получение элементов словаря по категории"""
        return self.vocabulary.get(category, [])

    def add_to_vocabulary(self, category, name):
        """Добавление нового элемента в контролируемый словарь"""
        if category not in self.vocabulary:
            self.vocabulary[category] = []

        # Проверяем, нет ли уже такого элемента
        for item in self.vocabulary[category]:
            if item.get('name') == name:
                return item

        # Создаем новый элемент
        import re
        # Транслитерация для ID
        latin_name = re.sub(r'[^\w\s-]', '', name)
        latin_name = re.sub(r'[-\s]+', '_', latin_name)
        new_id = f"{category[:-1]}_{latin_name.lower()}"

        new_item = {
            'id': new_id,
            'name': name
        }

        # Добавляем дополнительные поля для разных категорий
        if category == 'ethnos':
            new_item['alternative_names'] = []
            new_item['region'] = ''
        elif category == 'genres':
            new_item['local_terms'] = []
            new_item['ritual'] = False
        elif category == 'locations':
            new_item['type'] = 'other'
        elif category == 'collections':
            pass  # просто название
        elif category == 'instruments':
            new_item['type'] = 'other'
            new_item['local_names'] = []

        self.vocabulary[category].append(new_item)

        # Сохраняем в файл
        vocab_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "data", "controlled_vocabulary.json")
        with open(vocab_path, 'w', encoding='utf-8') as f:
            json.dump(self.vocabulary, f, ensure_ascii=False, indent=2)

        print(f"✅ Добавлен новый {category}: {name} (ID: {new_id})")
        return new_item