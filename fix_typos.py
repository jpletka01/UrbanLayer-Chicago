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
    
    replacements = [
        ("Valores De avalúos", "Valores de avalúo"),
        ("Estimación de Impuestos", "Proyección de impuestos"),
        ("Estimación de impuestos", "Proyección de impuestos"),
        ("Estimaciones de impuestos", "Proyecciones de impuestos"),
        ("Estimaciones de Impuestos", "Proyecciones de impuestos"),
        ("de avalúos", "de avalúo")
    ]

    for filename in os.listdir(base_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        replace_in_dict(data, replacements)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

process_all()
print("Fix typos complete")
