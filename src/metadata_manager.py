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
        self.FOLK = Namespace("http://folklorarchive.ru/folklor#")

        try:
            if not os.path.exists(ontology_path):
                print(f"⚠️ Файл онтологии не найден: {ontology_path}")
                self._create_basic_ontology()
            else:
                print(f"📂 Загрузка онтологии из {ontology_path}")
                self.g.parse(ontology_path, format="xml")
                print(f"✅ Онтология загружена. Триплетов: {len(self.g)}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке онтологии: {e}")
            traceback.print_exc()
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
            self.vocabulary = {
                'ethnos': [],
                'genres': [],
                'locations': [],
                'collections': [],
                'instruments': []
            }

    def _create_basic_ontology(self):
        """Создание базовой онтологии"""
        print("🔄 Создание базовой онтологии...")

        classes = [
            "АудиоЗапись", "Исполнитель", "Этнос", "Жанр",
            "ОбрядовыйСтатус", "Локация", "Инструмент", "Коллекция",
            "ФормаИсполнения"
        ]

        for class_name in classes:
            self.g.add((self.FOLK[class_name], RDF.type, OWL.Class))
            self.g.add((self.FOLK[class_name], RDFS.label, Literal(class_name, lang="ru")))

        ethical_flags = ["публичный_доступ", "ограниченный_доступ", "требует_согласия_общины"]
        for flag in ethical_flags:
            self.g.add((self.FOLK[flag], RDF.type, self.FOLK["ЭтическийСтатус"]))
            self.g.add((self.FOLK[flag], RDFS.label, Literal(flag, lang="ru")))

        print(f"✅ Базовая онтология создана. Триплетов: {len(self.g)}")

    def _determine_overall_performance_form(self, performers):
        """Определение общей формы исполнения для записи"""
        if not performers:
            return None

        has_vocal = False
        has_instrumental = False

        for performer in performers:
            form = performer.get('performance_form', '')
            if form == 'vocal':
                has_vocal = True
            elif form == 'instrumental':
                has_instrumental = True
            elif form == 'vocal_instrumental':
                return 'vocal_instrumental'

        if has_vocal and has_instrumental:
            return 'vocal_instrumental'
        elif has_vocal:
            return 'vocal'
        elif has_instrumental:
            return 'instrumental'
        else:
            return None

    def get_all_recordings(self):
        """Получение всех записей - ТОЛЬКО ИЗ JSON"""
        try:
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                     "data", "recordings.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    recordings = data.get('recordings', [])
                    if recordings:
                        print(f"✅ Загружено {len(recordings)} записей из JSON")

                        # Обрабатываем каждую запись
                        for rec in recordings:
                            # Определяем общую форму исполнения
                            performers = rec.get('performers', [])
                            overall_form = self._determine_overall_performance_form(performers)
                            rec['computed_performance_form'] = overall_form

                            # Для обратной совместимости
                            if 'performance_form' not in rec:
                                rec['performance_form'] = overall_form
                            if 'status' not in rec and 'ethical_status' in rec:
                                rec['status'] = rec['ethical_status']
                            elif 'status' not in rec:
                                rec['status'] = 'публичный_доступ'
                            if 'date' not in rec and 'recording_date' in rec:
                                rec['date'] = rec['recording_date']

                        return recordings

            return []
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
            'collection': {},
            'performance_form': {}
        }

        for rec in all_recordings:
            # Этносы (из исполнителей)
            for performer in rec.get('performers', []):
                if performer.get('ethnos'):
                    ethnos = performer['ethnos']
                    facets['ethnos'][ethnos] = facets['ethnos'].get(ethnos, 0) + 1

            # Жанры
            if rec.get('genre'):
                genre = rec['genre']
                facets['genre'][genre] = facets['genre'].get(genre, 0) + 1

            # Статусы
            status = rec.get('status') or rec.get('ethical_status')
            if status:
                facets['status'][status] = facets['status'].get(status, 0) + 1

            # Локации
            if rec.get('location'):
                location = rec['location']
                facets['location'][location] = facets['location'].get(location, 0) + 1

            # Коллекции
            if rec.get('collection'):
                collection = rec['collection']
                facets['collection'][collection] = facets['collection'].get(collection, 0) + 1

            # Форма исполнения (используем computed)
            perf_form = rec.get('computed_performance_form') or rec.get('performance_form')
            if perf_form:
                facets['performance_form'][perf_form] = facets['performance_form'].get(perf_form, 0) + 1

            # Десятилетия
            date_str = rec.get('date') or rec.get('recording_date')
            if date_str and '-' in date_str:
                try:
                    year = int(date_str.split('-')[0])
                    decade = (year // 10) * 10
                    decade_key = f"{decade}-{decade + 9}"
                    facets['decades'][decade_key] = facets['decades'].get(decade_key, 0) + 1
                except:
                    pass

        print(f"📊 Фасеты: {facets}")
        return facets

    def facet_search(self, filters=None, page=1, per_page=9, sort="title"):
        """Фасетный поиск с фильтрацией и пагинацией"""
        if filters is None:
            filters = {}

        all_recordings = self.get_all_recordings()
        print(f"🔍 Поиск с фильтрами: {filters}")
        print(f"📊 Всего записей: {len(all_recordings)}")

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
                rec_status = rec.get('status') or rec.get('ethical_status', '')
                if rec_status.lower() != filters['status'].lower():
                    match = False

            # Фильтр по локации
            if filters.get('location') and match:
                if rec.get('location', '').lower() != filters['location'].lower():
                    match = False

            # Фильтр по коллекции
            if filters.get('collection') and match:
                if rec.get('collection', '').lower() != filters['collection'].lower():
                    match = False

            # Фильтр по десятилетию
            if filters.get('decade') and match:
                date_str = rec.get('date') or rec.get('recording_date')
                if date_str and '-' in date_str:
                    try:
                        year = int(date_str.split('-')[0])
                        decade_start = (year // 10) * 10
                        decade_end = decade_start + 9
                        decade_key = f"{decade_start}-{decade_end}"
                        if decade_key != filters['decade']:
                            match = False
                    except:
                        match = False
                else:
                    match = False

            # Фильтр по форме исполнения
            if filters.get('performance_form') and match:
                perf_form = filters['performance_form']
                computed_form = rec.get('computed_performance_form') or rec.get('performance_form')

                # Если нет computed, определяем
                if not computed_form and rec.get('performers'):
                    has_vocal = False
                    has_instrumental = False
                    for performer in rec['performers']:
                        form = performer.get('performance_form', '')
                        if form == 'vocal':
                            has_vocal = True
                        elif form == 'instrumental':
                            has_instrumental = True
                        elif form == 'vocal_instrumental':
                            has_vocal = True
                            has_instrumental = True
                            break

                    if has_vocal and has_instrumental:
                        computed_form = 'vocal_instrumental'
                    elif has_vocal:
                        computed_form = 'vocal'
                    elif has_instrumental:
                        computed_form = 'instrumental'

                if computed_form != perf_form:
                    match = False

            # Фильтр по поисковому запросу
            if filters.get('search') and match:
                search_term = filters['search'].lower()
                title_match = search_term in rec.get('title', '').lower()
                performer_match = False
                for p in rec.get('performers', []):
                    if search_term in p.get('name', '').lower():
                        performer_match = True
                        break
                desc_match = search_term in rec.get('description', '').lower()
                if not (title_match or performer_match or desc_match):
                    match = False

            if match:
                filtered_results.append(rec)

        print(f"✅ После фильтрации: {len(filtered_results)} записей")

        # Сортировка
        if sort == "date_desc":
            filtered_results.sort(key=lambda x: x.get('date', '') or x.get('recording_date', ''), reverse=True)
        elif sort == "date_asc":
            filtered_results.sort(key=lambda x: x.get('date', '') or x.get('recording_date', ''))
        else:
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

    def add_recording(self, recording_data):
        """Добавление новой записи"""
        recordings = self._load_recordings_from_json()
        recording_id = self._get_next_id(recordings)

        instruments = recording_data.get('instruments', [])
        if instruments is None:
            instruments = []
        clean_instruments = []
        for inst in instruments:
            clean_inst = {'name': inst.get('name', '')}
            if clean_inst['name']:
                clean_instruments.append(clean_inst)

        recording = {
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
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        recordings.append(recording)

        if self._save_recordings_to_json(recordings):
            return recording_id
        return None

    def _load_recordings_from_json(self):
        """Загрузка записей из JSON"""
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "data", "recordings.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('recordings', [])
            except:
                pass
        return []

    def _save_recordings_to_json(self, recordings):
        """Сохранение записей в JSON"""
        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                 "data", "recordings.json")
        try:
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'total_recordings': len(recordings),
                'recordings': recordings
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Ошибка сохранения JSON: {e}")
            return False

    def _get_next_id(self, recordings):
        """Получение следующего ID"""
        if not recordings:
            return "1"
        max_id = 0
        for rec in recordings:
            try:
                rec_id = int(rec.get('id', 0))
                if rec_id > max_id:
                    max_id = rec_id
            except:
                pass
        return str(max_id + 1)

    def update_recording(self, recording_id, recording_data):
        """Обновление записи"""
        recordings = self._load_recordings_from_json()

        for i, rec in enumerate(recordings):
            if rec.get('id') == recording_id:
                recordings[i] = {
                    **rec,
                    'title': recording_data.get('title', rec.get('title', '')),
                    'inventory_number': recording_data.get('inventory_number', rec.get('inventory_number', '')),
                    'recording_date': recording_data.get('recording_date', rec.get('recording_date', '')),
                    'duration': recording_data.get('duration', rec.get('duration', '')),
                    'performers': recording_data.get('performers', rec.get('performers', [])),
                    'genre': recording_data.get('genre', rec.get('genre', '')),
                    'ethical_status': recording_data.get('ethical_status', rec.get('ethical_status', '')),
                    'location': recording_data.get('location', rec.get('location', '')),
                    'collection': recording_data.get('collection', rec.get('collection', '')),
                    'local_terms': recording_data.get('local_terms', rec.get('local_terms', [])),
                    'description': recording_data.get('description', rec.get('description', '')),
                    'updated_at': datetime.now().isoformat()
                }
                self._save_recordings_to_json(recordings)
                return True, "Запись обновлена"

        return False, "Запись не найдена"

    def delete_recording(self, recording_id):
        """Удаление записи"""
        recordings = self._load_recordings_from_json()

        for i, rec in enumerate(recordings):
            if rec.get('id') == recording_id:
                recordings.pop(i)
                self._save_recordings_to_json(recordings)
                return True, "Запись удалена"

        return False, "Запись не найдена"

    def export_to_mets(self, output_file="exports/mets.xml"):
        """Экспорт в METS"""
        try:
            import xml.etree.ElementTree as ET
            import xml.dom.minidom as minidom
        except ImportError:
            print("Ошибка: не удалось импортировать xml модули")
            return None

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        mets = ET.Element("mets")
        mets.set("xmlns", "http://www.loc.gov/METS/")

        metsHdr = ET.SubElement(mets, "metsHdr")
        metsHdr.set("CREATEDATE", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))

        agent = ET.SubElement(metsHdr, "agent")
        agent.set("ROLE", "CREATOR")
        agent.set("TYPE", "ORGANIZATION")
        agent.text = "ФонограммAрхив"

        dmdSec = ET.SubElement(mets, "dmdSec")
        dmdSec.set("ID", "DMD1")

        mdWrap = ET.SubElement(dmdSec, "mdWrap")
        mdWrap.set("MDTYPE", "DC")

        xmlData = ET.SubElement(mdWrap, "xmlData")
        recordings = self.get_all_recordings()
        records = ET.SubElement(xmlData, "records")

        for rec in recordings:
            record = ET.SubElement(records, "record")
            if rec.get('title'):
                title_elem = ET.SubElement(record, "title")
                title_elem.text = rec['title']
            if rec.get('inventory_number'):
                inv_elem = ET.SubElement(record, "identifier")
                inv_elem.set("type", "inventory_number")
                inv_elem.text = rec['inventory_number']
            if rec.get('date') or rec.get('recording_date'):
                date_elem = ET.SubElement(record, "date")
                date_elem.text = rec.get('date') or rec.get('recording_date')
            for performer in rec.get('performers', []):
                if performer.get('name'):
                    creator_elem = ET.SubElement(record, "creator")
                    creator_text = performer['name']
                    if performer.get('ethnos'):
                        creator_text += f" ({performer['ethnos']})"
                    creator_elem.text = creator_text

        xml_str = ET.tostring(mets, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')

        with open(output_file, 'wb') as f:
            f.write(pretty_xml)

        return output_file

    def get_vocabulary(self):
        return self.vocabulary

    def get_vocabulary_by_category(self, category):
        return self.vocabulary.get(category, [])

    def add_to_vocabulary(self, category, name):
        if category not in self.vocabulary:
            self.vocabulary[category] = []

        for item in self.vocabulary[category]:
            if item.get('name') == name:
                return item

        latin_name = re.sub(r'[^\w\s-]', '', name)
        latin_name = re.sub(r'[-\s]+', '_', latin_name)
        new_id = f"{category[:-1]}_{latin_name.lower()}"

        new_item = {'id': new_id, 'name': name}

        if category == 'ethnos':
            new_item['alternative_names'] = []
            new_item['region'] = ''
        elif category == 'genres':
            new_item['local_terms'] = []
            new_item['ritual'] = False
        elif category == 'locations':
            new_item['type'] = 'other'
        elif category == 'collections':
            pass
        elif category == 'instruments':
            new_item['type'] = 'other'
            new_item['local_names'] = []

        self.vocabulary[category].append(new_item)

        vocab_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  "data", "controlled_vocabulary.json")
        with open(vocab_path, 'w', encoding='utf-8') as f:
            json.dump(self.vocabulary, f, ensure_ascii=False, indent=2)

        return new_item