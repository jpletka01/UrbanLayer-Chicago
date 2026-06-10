import json
import os

def replace_in_dict(d, replacements):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, str):
                for old, new in replacements:
                    d[k] = d[k].replace(old, new)
            else:
                replace_in_dict(v, replacements)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            if isinstance(v, str):
                for old, new in replacements:
                    d[i] = d[i].replace(old, new)
            else:
                replace_in_dict(v, replacements)

def process_all():
    base_dir = "frontend/src/locales/es"
    
    global_replacements = [
        # Domain Nouns instead of descriptive
        ("Capacidad de construcción", "Edificabilidad"),
        ("Valor estimado", "Valoración"),
        ("Riesgos a considerar", "Riesgos"),
        
        # Compression and rhythm
        ("Consultar una dirección para obtener el panorama completo.", "Consulta una dirección y obtén el panorama completo."),
        ("Realizar en segundos la auditoría de compra que normalmente tomaría una semana.", "Auditoría de compra en segundos, no en semanas."),
        ("Consultar en español sin utilizar lenguajes complejos ni configurar formularios.", "Consulta en español. Sin sintaxis compleja ni formularios."),
        ("Obtener una respuesta documentada con citas, mapas interactivos y análisis regulatorio, con la opción de descargar un informe profesional.", "Respuestas documentadas con citas, mapas interactivos y análisis normativo. Generación directa de informes profesionales."),
        
        # Glossary lock
        ("Regulaciones superpuestas", "Normativas superpuestas"),
        ("regulaciones superpuestas", "normativas superpuestas"),
        ("Regulaciones", "Normativas"),
        ("regulaciones", "normativas"),
        ("Regulatorio", "Normativo"),
        ("regulatorio", "normativo"),
        ("Valores de avalúo", "Avalúos"),
        ("valor de avalúo", "avalúo"),
        ("inmueble", "propiedad"),
        ("Inmueble", "Propiedad")
    ]

    for filename in os.listdir(base_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        replace_in_dict(data, global_replacements)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

process_all()
print("Final polish complete")
