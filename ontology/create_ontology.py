# ontology/create_ontology.py (альтернативная версия)
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
import os

# Создаем граф
g = Graph()

# Определяем пространства имен
FOLK = Namespace("http://agiki.ru/folklor#")
g.bind("folk", FOLK)
g.bind("owl", OWL)
g.bind("rdfs", RDFS)

# Базовые классы
classes = [
    ("АудиоЗапись", "Цифровая аудиозапись фольклорного материала"),
    ("Исполнитель", "Лицо, исполняющее фольклорное произведение"),
    ("Этнос", "Этническая группа"),
    ("Жанр", "Музыкально-фольклорный жанр"),
    ("ОбрядовыйСтатус", "Статус обрядового действия"),
    ("Локация", "Место записи"),
    ("Инструмент", "Музыкальный инструмент"),
    ("Коллекция", "Архивная коллекция записей")
]

for class_name, comment in classes:
    g.add((FOLK[class_name], RDF.type, OWL.Class))
    g.add((FOLK[class_name], RDFS.label, Literal(class_name, lang="ru")))
    g.add((FOLK[class_name], RDFS.comment, Literal(comment, lang="ru")))

# Этические флаги
ethical_flags = ["публичный_доступ", "ограниченный_доступ", "требует_согласия_общины"]
for flag in ethical_flags:
    g.add((FOLK[flag], RDF.type, FOLK["ЭтическийСтатус"]))
    g.add((FOLK[flag], RDFS.label, Literal(flag, lang="ru")))

# Определяем путь для сохранения
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
output_path = os.path.join(project_root, "ontology", "folklor_ontology.owl")

# Создаем папку ontology в корне проекта
os.makedirs(os.path.join(project_root, "ontology"), exist_ok=True)

# Сохраняем онтологию
g.serialize(destination=output_path, format="xml")
print(f"✅ Онтология создана и сохранена в {output_path}")
print(f"   Количество триплетов: {len(g)}")