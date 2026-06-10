import json
import os
import re

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
        # Numbers instead of words
        ("Veinticinco", "25"),
        ("veinticinco", "25"),
        
        # Tone adjustments (tú instead of infinitive)
        ("Iniciar sesión para continuar", "Inicia sesión para continuar"),
        ("Crear una cuenta", "Crea una cuenta"),
        ("Escribir una consulta de seguimiento", "Escribe una consulta de seguimiento"),
        ("Evaluar cualquier sitio", "Evalúa cualquier sitio"),
        ("Seleccionar un área comunitaria o ingresar", "Selecciona un área comunitaria o ingresa"),
        ("Ingresar una dirección...", "Ingresa una dirección..."),
        ("Ingresar una dirección de Chicago", "Ingresa una dirección de Chicago"),
        ("Explorar parcelas", "Explora parcelas"),
        ("Consultar una dirección y obtén", "Consulta una dirección y obtén"),
        ("Descargar un informe profesional", "Descarga un informe profesional"),
        
        # Data Labels
        ("Ocupada por el prop.", "Propietario-ocupada"),
        ("Impuestos est.", "Impuesto anual estimado"),
        ("Imp. Est.", "Impuesto anual estimado"),
        
        # Specific phrasing requests
        ("que necesita conocer antes de comprometer capital", "que debes conocer antes de invertir"),
        ("que necesita conocer antes de invertir", "que debes conocer antes de invertir"),
        ("interpretación del código por IA", "interpretación del código impulsada por IA"),
        ("retiros y FAR", "retiros (setbacks) y FAR"),
        ("Normativas superpuestas, alertas ambientales, infracciones de edificios e historial de permisos", "Normativas superpuestas, alertas ambientales, infracciones de edificios, historial de permisos")
    ]

    for filename in os.listdir(base_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        replace_in_dict(data, global_replacements)
        
        if filename == "landing.json":
            if "valueProps" in data:
                data["valueProps"]["buildTitle"] = "Qué puedes construir"
                data["valueProps"]["worthTitle"] = "Cuánto vale"
                data["valueProps"]["watchTitle"] = "Qué debes vigilar"
                
                if "watchBody" in data["valueProps"]:
                    data["valueProps"]["watchBody"] = data["valueProps"]["watchBody"].replace(
                        "Los riesgos y oportunidades que necesita conocer antes de comprometer capital", 
                        "Los riesgos y oportunidades que debes conocer antes de invertir"
                    )
            
            if "howItWorks" in data and "steps" in data["howItWorks"]:
                steps = data["howItWorks"]["steps"]
                if len(steps) >= 3:
                    steps[0]["description"] = "Haz tus consultas en español, sin sintaxis compleja ni formularios."
                    steps[1]["description"] = "Tu consulta activa las fuentes de datos del municipio, condado y gobierno federal en paralelo."
                    steps[2]["description"] = "Obtén respuestas documentadas con citas, mapas interactivos y análisis normativo. Descarga directa de informes profesionales."

            if "story" in data:
                if "feasibilityTitle" in data["story"]:
                    data["story"]["feasibilityTitle"] = "Evalúa cualquier sitio en segundos"
                if "reportSubtitle" in data["story"]:
                    data["story"]["reportSubtitle"] = "Haz tus consultas en español y obtén un análisis detallado con fuentes citadas del código municipal, mapas interactivos y tendencias de datos. Descarga un informe profesional en PDF para clientes, inversores o prestamistas."
                    
            if "depth" in data and "heading" in data["depth"]:
                data["depth"]["heading"] = "Haz tu consulta y obtén el panorama completo."

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

process_all()
print("Marketing pass complete")
