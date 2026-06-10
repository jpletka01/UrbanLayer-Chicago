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

def process_landing():
    filepath = "frontend/src/locales/es/landing.json"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 1. Concept hierarchy
    if "valueProps" in data:
        data["valueProps"]["worthTitle"] = "Valoración inmobiliaria"
        data["valueProps"]["watchTitle"] = "Riesgo normativo"
        
        # 2. UI Rhythm
        data["valueProps"]["buildBody"] = "Clasificación de zonificación instantánea con interpretación del código por IA. Permite consultar usos permitidos, retiros y FAR, con respuestas citadas de más de 14,000 secciones del código municipal."

    # 3. Standardize "consulta" drift
    # 4. Micro UX phrasing
    if "howItWorks" in data and "steps" in data["howItWorks"]:
        steps = data["howItWorks"]["steps"]
        if len(steps) == 3:
            steps[0]["title"] = "Ingresa tu consulta"
            steps[0]["description"] = "Consulta en español, sin formularios ni sintaxis compleja."
            steps[1]["description"] = "Tu consulta activa simultáneamente la combinación adecuada de fuentes de datos a nivel municipal, del condado y federal."
            
    # 5. Data list compression
    if "howItWorks" in data and "sourceTags" in data["howItWorks"]:
        data["howItWorks"]["sourceTags"] = [
            "Zonificación",
            "Normativas",
            "Propiedad",
            "Permisos",
            "TIF",
            "Código municipal",
            "Incentivos",
            "Impuestos"
        ]
        
    # 6. Over-preservation of contrast
    if "story" in data and "feasibilitySubtitle" in data["story"]:
        data["story"]["feasibilitySubtitle"] = data["story"]["feasibilitySubtitle"].replace("en segundos, no en semanas.", "en segundos, no en semanas de trabajo.")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

process_landing()
print("Perfection pass complete")
