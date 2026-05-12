from flask import Flask, render_template, request, jsonify, send_file
from src.metadata_manager import FolklorMetadataManager
from datetime import datetime
import json, os, traceback, uuid, re
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ONTOLOGY_PATH = os.path.join(BASE_DIR, "ontology", "folklor_ontology.owl")
DATA_PATH     = os.path.join(BASE_DIR, "data", "recordings.json")
VOCAB_PATH    = os.path.join(BASE_DIR, "data", "controlled_vocabulary.json")
EXPORTS_DIR   = os.path.join(BASE_DIR, "exports")
UPLOADS_DIR   = os.path.join(BASE_DIR, "uploads")

os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_AUDIO = {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'}
ALLOWED_VIDEO = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'wmv', 'flv'}
ALLOWED_EXT   = ALLOWED_AUDIO | ALLOWED_VIDEO

app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

manager = FolklorMetadataManager(ontology_path=ONTOLOGY_PATH)


# ── helpers ──────────────────────────────────────────────────────

def ext_of(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def file_type(filename):
    e = ext_of(filename)
    return 'audio' if e in ALLOWED_AUDIO else ('video' if e in ALLOWED_VIDEO else 'unknown')

def load_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d, d.get('recordings', [])
    return {'version': '1.0', 'recordings': []}, []

def save_data(recordings):
    d = {'version': '1.0', 'last_updated': datetime.now().isoformat(),
         'total_recordings': len(recordings), 'recordings': recordings}
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def save_recording(data, rec_id=None):
    _, recs = load_data()
    if not rec_id:
        rec_id = f"rec_{uuid.uuid4().hex[:8]}"
    idx = next((i for i, r in enumerate(recs) if r.get('id') == rec_id), None)
    now = datetime.now().isoformat()

    performers = [
        {'name': p['name'].strip(),
         'ethnos': p.get('ethnos') or None,
         'performance_form': p.get('performance_form', ''),
         'instruments': [{'name': i['name'].strip()}
                         for i in p.get('instruments', []) if i.get('name', '').strip()]}
        for p in data.get('performers', []) if p.get('name', '').strip()
    ]

    rec = {
        'id': rec_id,
        'title':            data.get('title', '').strip(),
        'inventory_number': data.get('inventory_number', '').strip(),
        'recording_date':   data.get('recording_date', ''),
        'duration':         data.get('duration', ''),
        'performers':       performers,
        'genre':            data.get('genre', ''),
        'ethical_status':   data.get('ethical_status', 'публичный_доступ'),
        'location':         data.get('location', ''),
        'collection':       data.get('collection', ''),
        'local_terms':      [t.strip() for t in data.get('local_terms', []) if str(t).strip()],
        'description':      data.get('description', '').strip(),
        'updated_at':       now,
    }
    if idx is not None:
        old = recs[idx]
        rec['created_at']   = old.get('created_at', now)
        rec['media_files']  = data.get('media_files', old.get('media_files', []))
        recs[idx] = rec
    else:
        rec['created_at']  = now
        rec['media_files'] = data.get('media_files', [])
        recs.append(rec)
    save_data(recs)
    return rec_id

def delete_recording_data(rec_id):
    _, recs = load_data()
    new = [r for r in recs if r.get('id') != rec_id]
    if len(new) < len(recs):
        save_data(new); return True
    return False

def validate_duration(dur):
    if not dur or not dur.strip(): return True, ""
    if not re.match(r'^([0-9]{1,3}:)?[0-5]?[0-9]:[0-5][0-9]$', dur.strip()):
        return False, "Формат: ММ:СС или ЧЧ:ММ:СС"
    p = dur.strip().split(':')
    if len(p) == 3 and int(p[0]) > 99:
        return False, "Часы не могут быть больше 99"
    return True, ""

def save_vocab(fv):
    manager.vocabulary = fv
    with open(VOCAB_PATH, 'w', encoding='utf-8') as f:
        json.dump(fv, f, ensure_ascii=False, indent=2)

def init_data():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            d = json.load(f)
        for r in d.get('recordings', []):
            if not manager.get_recording_by_id(r.get('id')):
                manager.add_recording(r)

init_data()
VOCAB_CATS = ['ethnos', 'genres', 'locations', 'collections', 'instruments']


# ── pages ─────────────────────────────────────────────────────────

@app.route('/')
def index(): return render_template('index.html')

@app.route('/add_recording')
def add_recording_page(): return render_template('add_recording.html')

@app.route('/edit_recording/<rid>')
def edit_recording_page(rid): return render_template('edit_recording.html', recording_id=rid)

@app.route('/recording/<rid>')
def recording_detail(rid): return render_template('recording_detail.html', recording_id=rid)

@app.route('/vocabulary')
def vocabulary_page(): return render_template('vocabulary.html')


# ── search ────────────────────────────────────────────────────────

@app.route('/api/facet_search')
def api_facet_search():
    filters = {k: request.args[k] for k in
               ('ethnos','genre','status','location','collection','decade','performance_form')
               if request.args.get(k)}
    if request.args.get('q'): filters['search'] = request.args['q']
    return jsonify(manager.facet_search(
        filters=filters,
        page=int(request.args.get('page', 1)),
        sort=request.args.get('sort', 'title')
    ))

@app.route('/api/facets')
def api_facets(): return jsonify(manager.get_facet_counts())


# ── recordings CRUD ───────────────────────────────────────────────

@app.route('/api/add_recording', methods=['POST'])
def api_add_recording():
    try:
        data = request.json
        ok, msg = validate_duration(data.get('duration', ''))
        if not ok: return jsonify({'status':'error','message':msg}), 400
        rid = save_recording(data)
        if not manager.get_recording_by_id(rid):
            manager.add_recording({**data, 'id': rid})
        return jsonify({'status':'success','id':rid})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 400

@app.route('/api/recording/<rid>')
def api_get_recording(rid):
    try:
        _, recs = load_data()
        for r in recs:
            if r.get('id') == rid:
                return jsonify({
                    'id': r['id'], 'title': r.get('title',''),
                    'inventory_number': r.get('inventory_number',''),
                    'date':   r.get('recording_date','') or r.get('date',''),
                    'duration': r.get('duration',''),
                    'status': r.get('ethical_status','') or r.get('status','публичный_доступ'),
                    'genre': r.get('genre',''), 'location': r.get('location',''),
                    'collection': r.get('collection',''), 'description': r.get('description',''),
                    'local_terms': r.get('local_terms',[]),
                    'performers': r.get('performers',[]),
                    'media_files': r.get('media_files',[]),
                    'created_at': r.get('created_at',''), 'updated_at': r.get('updated_at',''),
                })
        r = manager.get_recording_by_id(rid)
        if r: r.setdefault('media_files',[]); return jsonify(r)
        return jsonify({'error':'Запись не найдена'}), 404
    except Exception as e:
        traceback.print_exc(); return jsonify({'error':str(e)}), 500

@app.route('/api/update_recording/<rid>', methods=['POST'])
def api_update_recording(rid):
    try:
        data = request.json
        ok, msg = validate_duration(data.get('duration',''))
        if not ok: return jsonify({'status':'error','message':msg}), 400
        save_recording(data, rid)
        ok2, msg2 = manager.update_recording(rid, data)
        return jsonify({'status':'success' if ok2 else 'error','message':msg2})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/delete_recording/<rid>', methods=['DELETE'])
def api_delete_recording(rid):
    try:
        _, recs = load_data()
        for r in recs:
            if r.get('id') == rid:
                for mf in r.get('media_files',[]):
                    if mf.get('type') == 'file':
                        fp = os.path.join(UPLOADS_DIR, mf.get('stored_name',''))
                        if os.path.exists(fp): os.remove(fp)
                break
        delete_recording_data(rid)
        ok, msg = manager.delete_recording(rid)
        return jsonify({'status':'success' if ok else 'error','message':msg})
    except Exception as e:
        return jsonify({'status':'error','message':str(e)}), 500


# ── media upload ──────────────────────────────────────────────────

@app.route('/api/recording/<rid>/upload_media', methods=['POST'])
def api_upload_media(rid):
    try:
        if 'file' not in request.files:
            return jsonify({'status':'error','message':'Файл не найден'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'status':'error','message':'Пустое имя файла'}), 400
        original = secure_filename(file.filename)
        e = ext_of(original)
        if e not in ALLOWED_EXT:
            return jsonify({'status':'error',
                'message':f'Недопустимый формат. Разрешены: {", ".join(sorted(ALLOWED_EXT))}'}), 400

        _, recs = load_data()
        idx = next((i for i,r in enumerate(recs) if r.get('id') == rid), None)
        if idx is None:
            return jsonify({'status':'error','message':'Запись не найдена'}), 404

        stored = f"{rid}_{uuid.uuid4().hex[:8]}.{e}"
        path   = os.path.join(UPLOADS_DIR, stored)
        file.save(path)
        size = os.path.getsize(path)

        entry = {
            'id': uuid.uuid4().hex[:8], 'type': 'file',
            'original_name': original, 'stored_name': stored,
            'file_type': file_type(original), 'size': size,
            'uploaded_at': datetime.now().isoformat(),
        }
        recs[idx].setdefault('media_files', []).append(entry)
        recs[idx]['updated_at'] = datetime.now().isoformat()
        save_data(recs)
        return jsonify({'status':'success','media':entry})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500


# ── media link ────────────────────────────────────────────────────

@app.route('/api/recording/<rid>/add_media_link', methods=['POST'])
def api_add_media_link(rid):
    """Добавление медиа по внешней ссылке"""
    try:
        data = request.json
        url  = (data.get('url') or '').strip()
        label = (data.get('label') or '').strip()
        ft   = data.get('file_type', 'video')   # 'audio' | 'video'

        if not url:
            return jsonify({'status':'error','message':'URL не указан'}), 400
        if not re.match(r'^https?://', url):
            return jsonify({'status':'error','message':'URL должен начинаться с http:// или https://'}), 400

        _, recs = load_data()
        idx = next((i for i,r in enumerate(recs) if r.get('id') == rid), None)
        if idx is None:
            return jsonify({'status':'error','message':'Запись не найдена'}), 404

        entry = {
            'id': uuid.uuid4().hex[:8], 'type': 'link',
            'url': url, 'label': label or url,
            'file_type': ft,
            'added_at': datetime.now().isoformat(),
        }
        recs[idx].setdefault('media_files', []).append(entry)
        recs[idx]['updated_at'] = datetime.now().isoformat()
        save_data(recs)
        return jsonify({'status':'success','media':entry})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500


# ── media delete / serve ──────────────────────────────────────────

@app.route('/api/recording/<rid>/delete_media/<mid>', methods=['DELETE'])
def api_delete_media(rid, mid):
    try:
        _, recs = load_data()
        idx = next((i for i,r in enumerate(recs) if r.get('id') == rid), None)
        if idx is None: return jsonify({'status':'error','message':'Запись не найдена'}), 404
        ml  = recs[idx].get('media_files', [])
        entry = next((m for m in ml if m.get('id') == mid), None)
        if not entry: return jsonify({'status':'error','message':'Файл не найден'}), 404
        if entry.get('type') == 'file':
            fp = os.path.join(UPLOADS_DIR, entry['stored_name'])
            if os.path.exists(fp): os.remove(fp)
        recs[idx]['media_files'] = [m for m in ml if m.get('id') != mid]
        recs[idx]['updated_at']  = datetime.now().isoformat()
        save_data(recs)
        return jsonify({'status':'success'})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/media/<stored_name>')
def api_serve_media(stored_name):
    fp = os.path.join(UPLOADS_DIR, secure_filename(stored_name))
    if not os.path.exists(fp): return jsonify({'error':'Файл не найден'}), 404
    return send_file(fp)

@app.route('/api/media/<stored_name>/download')
def api_download_media(stored_name):
    safe = secure_filename(stored_name)
    fp   = os.path.join(UPLOADS_DIR, safe)
    if not os.path.exists(fp): return jsonify({'error':'Файл не найден'}), 404
    # Ищем оригинальное имя
    original = safe
    _, recs = load_data()
    for r in recs:
        for mf in r.get('media_files', []):
            if mf.get('stored_name') == safe:
                original = mf.get('original_name', safe); break
    return send_file(fp, as_attachment=True, download_name=original)


# ── vocabulary ────────────────────────────────────────────────────

@app.route('/api/vocabulary/<cat>')
def api_get_vocab(cat): return jsonify(manager.get_vocabulary_by_category(cat))

@app.route('/api/add_to_vocabulary', methods=['POST'])
def api_add_to_vocab():
    try:
        d = request.json; cat = d.get('category'); name = d.get('name','').strip()
        if not cat or not name: return jsonify({'error':'Не указаны параметры'}), 400
        if cat not in VOCAB_CATS: return jsonify({'error':'Недопустимая категория'}), 400
        return jsonify({'status':'success','item': manager.add_to_vocabulary(cat, name)})
    except Exception as e: return jsonify({'error':str(e)}), 500

@app.route('/api/vocabulary/<cat>/add_item', methods=['POST'])
def api_vocab_add_item(cat):
    try:
        if cat not in VOCAB_CATS: return jsonify({'status':'error','message':'Недопустимая категория'}), 400
        d = request.json; name = d.get('name','').strip()
        if not name: return jsonify({'status':'error','message':'Название обязательно'}), 400
        fv = manager.vocabulary; vocab = fv.get(cat, [])
        if any(i.get('name','').lower() == name.lower() for i in vocab):
            return jsonify({'status':'error','message':'Уже существует'}), 409
        raw = re.sub(r'[^\w]', '_', name.lower())
        prefix = cat.rstrip('s') if cat.endswith('s') else cat
        new_item = {'id': f"{prefix}_{raw}", 'name': name}
        if cat == 'ethnos':    new_item.update({'alternative_names': d.get('alternative_names',[]), 'region': d.get('region','')})
        elif cat == 'genres':  new_item.update({'local_terms': d.get('local_terms',[]), 'ritual': d.get('ritual', False)})
        elif cat == 'locations': new_item['type'] = d.get('type','other')
        elif cat == 'instruments': new_item.update({'type': d.get('type','other'), 'local_names': d.get('local_names',[])})
        vocab.append(new_item); fv[cat] = vocab; save_vocab(fv)
        return jsonify({'status':'success','item':new_item})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/vocabulary/<cat>/update', methods=['POST'])
def api_vocab_update(cat):
    try:
        d = request.json; iid = d.get('id'); updates = d.get('updates',{})
        if not iid: return jsonify({'status':'error','message':'Не указан ID'}), 400
        fv = manager.vocabulary
        for item in fv.get(cat, []):
            if item.get('id') == iid:
                item.update(updates); save_vocab(fv); return jsonify({'status':'success'})
        return jsonify({'status':'error','message':'Элемент не найден'}), 404
    except Exception as e: return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/vocabulary/<cat>/delete', methods=['DELETE'])
def api_vocab_delete(cat):
    try:
        if cat not in VOCAB_CATS: return jsonify({'status':'error','message':'Недопустимая категория'}), 400
        iid = request.json.get('id')
        if not iid: return jsonify({'status':'error','message':'Не указан ID'}), 400
        fv = manager.vocabulary; vocab = fv.get(cat, [])
        new = [i for i in vocab if i.get('id') != iid]
        if len(new) == len(vocab): return jsonify({'status':'error','message':'Не найден'}), 404
        fv[cat] = new; save_vocab(fv); return jsonify({'status':'success'})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/vocabulary/<cat>/add_term', methods=['POST'])
def api_vocab_add_term(cat):
    try:
        d = request.json; iid = d.get('id'); field = d.get('field'); term = d.get('term','').strip()
        if not all([iid, field, term]): return jsonify({'status':'error','message':'Не указаны параметры'}), 400
        fv = manager.vocabulary
        for item in fv.get(cat, []):
            if item.get('id') == iid:
                item.setdefault(field, [])
                if term not in item[field]: item[field].append(term)
                save_vocab(fv); return jsonify({'status':'success'})
        return jsonify({'status':'error','message':'Не найден'}), 404
    except Exception as e: return jsonify({'status':'error','message':str(e)}), 500

@app.route('/api/vocabulary/<cat>/remove_term', methods=['POST'])
def api_vocab_remove_term(cat):
    try:
        d = request.json; iid = d.get('id'); field = d.get('field'); term = d.get('term')
        if not all([iid, field, term]): return jsonify({'status':'error','message':'Не указаны параметры'}), 400
        fv = manager.vocabulary
        for item in fv.get(cat, []):
            if item.get('id') == iid:
                if field in item and term in item[field]: item[field].remove(term)
                save_vocab(fv); return jsonify({'status':'success'})
        return jsonify({'status':'error','message':'Не найден'}), 404
    except Exception as e: return jsonify({'status':'error','message':str(e)}), 500

# ── local terms in recordings ──────────────────────────────────────

@app.route('/api/local_terms_all')
def api_local_terms_all():
    """Все местные термины из всех записей с контекстом"""
    try:
        _, recs = load_data()
        result = []
        seen = {}
        for r in recs:
            for term in r.get('local_terms', []):
                if not term.strip(): continue
                key = term.lower()
                if key not in seen:
                    seen[key] = {'term': term, 'alt_names': [], 'recordings': []}
                seen[key]['recordings'].append({'id': r['id'], 'title': r.get('title','')})
        # Загружаем сохранённые alt_names для терминов
        lt_vocab = manager.vocabulary.get('local_terms_meta', {})
        for key, item in seen.items():
            item['alt_names'] = lt_vocab.get(key, {}).get('alt_names', [])
            result.append(item)
        result.sort(key=lambda x: x['term'].lower())
        return jsonify(result)
    except Exception as e:
        traceback.print_exc(); return jsonify({'error':str(e)}), 500

@app.route('/api/local_terms_meta/update', methods=['POST'])
def api_lt_meta_update():
    """Сохранение/обновление альтернативных названий для термина"""
    try:
        d    = request.json
        term = d.get('term','').strip()
        alts = d.get('alt_names', [])
        if not term: return jsonify({'status':'error','message':'Термин не указан'}), 400
        fv = manager.vocabulary
        fv.setdefault('local_terms_meta', {})
        key = term.lower()
        fv['local_terms_meta'][key] = {'term': term, 'alt_names': alts}
        save_vocab(fv)
        return jsonify({'status':'success'})
    except Exception as e:
        traceback.print_exc(); return jsonify({'status':'error','message':str(e)}), 500


# ── export ────────────────────────────────────────────────────────

@app.route('/api/export_mets')
def api_export_mets():
    try:
        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = os.path.join(EXPORTS_DIR, f"mets_{ts}.xml")
        manager.export_to_mets(out)
        if os.path.exists(out):
            return send_file(out, as_attachment=True, download_name=f"mets_{ts}.xml")
        return jsonify({'status':'error','message':'Файл не создан'}), 500
    except Exception as e: return jsonify({'status':'error','message':str(e)}), 500

@app.route('/debug/recordings')
def debug_recordings():
    recs = manager.get_all_recordings()
    return jsonify({'count': len(recs), 'recordings': recs})


if __name__ == '__main__':
    print("🚀 http://localhost:5000")
    app.run(debug=True, port=5000)