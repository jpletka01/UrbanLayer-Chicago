import json
import re

def replace_in_dict(d, replacements):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, str):
                for old, new in replacements:
                    # using word boundary or precise match if it's the exact string
                    if v == old:
                        d[k] = new
                    else:
                        d[k] = v.replace(old, new)
            else:
                replace_in_dict(v, replacements)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            if isinstance(v, str):
                for old, new in replacements:
                    if v == old:
                        d[i] = new
                    else:
                        d[i] = v.replace(old, new)
            else:
                replace_in_dict(v, replacements)

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    replacements = [
        ("Valor tasado", "Avalúo"),
        ("Historial de tasación", "Historial de avalúos"),
        ("Impuesto anual est.", "Impuesto anual estimado"),
        ("Regulatorio", "Normativas"),
        ("Regulaciones superpuestas", "Normativas superpuestas"),
        ("Sitios contaminados cercanos", "Terrenos industriales abandonados cercanos"),
        ("Ingreso med.", "Ingreso medio"),
        ("Edad mediana", "Edad media"),
        ("Renta mediana", "Renta media"),
        ("Caminata", "Tránsito peatonal"),
        ("Transporte", "Transporte público"),
        ("Bicicleta", "Tránsito en bicicleta"),
        ("Edificios vacantes", "Edificios desocupados"),
        ("Tasa de arresto", "Tasa de arrestos"),
        ("Propietarios", "Ocupado por el propietario"),
        ("Licenciatura+", "Licenciatura o superior"),
        ("Valores tasados", "Valores catastrales"),
        ("Tasas de arresto", "Tasa de arrestos"),
        ("Plomería", "Plomería"),
        ("Elevador", "Ascensor"),
        ("Escalera mecánica", "Escalera mecánica"),
        ("Ingresos por impuesto predial", "Ingresos por impuesto a la propiedad"),
        ("No en zona de oportunidad", "Fuera de la zona de oportunidad"),
        ("En distrito TIF", "Dentro de un distrito TIF"),
        ("No en TIF", "Fuera del distrito TIF"),
        ("No criminal", "No delictivo"),
        ("No criminal (sujeto especificado)", "No delictivo (sujeto especificado)"),
        ("Delito con menores", "Delitos contra menores")
    ]
    
    replace_in_dict(data, replacements)
    
    # Specific targeted replacements for data.json
    if "regulatory" in data and "overlays" in data["regulatory"]:
        if data["regulatory"]["overlays"] == "Regulaciones":
            data["regulatory"]["overlays"] = "Normativas superpuestas"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

process_file("frontend/src/locales/es/data.json")
process_file("frontend/src/locales/es/map.json")
print("Update complete")
