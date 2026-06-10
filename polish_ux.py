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
    
    # Define exact substring replacements for UX tone
    global_replacements = [
        # Impersonal Tone normalization
        ("Inicie sesión para continuar", "Iniciar sesión para continuar"),
        ("Cree una cuenta para guardar sus", "Crear una cuenta para guardar las"),
        ("Haga una consulta de seguimiento", "Escribir una consulta de seguimiento"),
        ("Evalúe cualquier sitio", "Evaluar cualquier sitio"),
        ("Realice una consulta en español. Obtenga un", "Consultar en español para obtener un"),
        ("Seleccione un área comunitaria o ingrese", "Seleccionar un área comunitaria o ingresar"),
        ("Ingrese una dirección...", "Ingresar una dirección..."),
        ("Pregunte qué está permitido", "Consultar sobre usos permitidos"),
        ("obtenga respuestas citadas", "obtener respuestas citadas"),
        
        # Controlled Vocabulary
        ("regulaciones superpuestas", "normativas superpuestas"),
        ("Regulaciones superpuestas", "Normativas superpuestas"),
        ("capas de superposición", "normativas superpuestas"),
        ("cumplimiento del código", "cumplimiento de normativas"),
        ("Cumplimiento del código", "Cumplimiento de normativas")
    ]

    for filename in os.listdir(base_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        replace_in_dict(data, global_replacements)
        
        # Specific structural changes
        if filename == "landing.json":
            # valueProps - native UI headers
            if "valueProps" in data:
                data["valueProps"]["buildTitle"] = "Capacidad de construcción"
                data["valueProps"]["worthTitle"] = "Valor estimado"
                data["valueProps"]["watchTitle"] = "Riesgos a considerar"
            
            # Formality & Rhythm
            if "intelligence" in data and "heading" in data["intelligence"]:
                data["intelligence"]["heading"] = "Veinticinco fuentes en una sola consulta."
            
            if "story" in data:
                if "reportTitle" in data["story"]:
                    data["story"]["reportTitle"] = "Generación de informes a partir de análisis"
                if "feasibilitySubtitle" in data["story"]:
                    data["story"]["feasibilitySubtitle"] = "Clasificación de zonificación, normativas superpuestas, elegibilidad de incentivos, proyecciones de impuestos y propiedades comparables consolidadas desde más de 25 fuentes. Realizar en segundos la auditoría de compra que normalmente tomaría una semana."
                if "reportSubtitle" in data["story"]:
                    data["story"]["reportSubtitle"] = "Consultar en español para obtener un análisis detallado con fuentes citadas del código municipal, mapas interactivos y tendencias de datos. Descargar un informe profesional en PDF para clientes, inversores o prestamistas."
            
            if "depth" in data and "heading" in data["depth"]:
                data["depth"]["heading"] = "Consultar una dirección para obtener el panorama completo."
                
            if "howItWorks" in data and "steps" in data["howItWorks"]:
                steps = data["howItWorks"]["steps"]
                if len(steps) == 3:
                    steps[0]["title"] = "Ingreso de consulta"
                    steps[0]["description"] = "Consultar en español sin utilizar lenguajes complejos ni configurar formularios."
                    steps[1]["title"] = "Procesamiento de datos"
                    steps[1]["description"] = "La consulta activa simultáneamente la combinación adecuada de fuentes de datos a nivel municipal, del condado y federal."
                    steps[2]["title"] = "Resultados detallados"
                    steps[2]["description"] = "Obtener una respuesta documentada con citas, mapas interactivos y análisis regulatorio, con la opción de descargar un informe profesional."
                    
            if "personas" in data and "returns" in data["personas"]:
                data["personas"]["returns"] = "UrbanLayer proporciona:"
        
        elif filename == "pages.json":
            if "scorecard" in data and "subtitle" in data["scorecard"]:
                data["scorecard"]["subtitle"] = "Inteligencia de propiedades al instante. Ingresar una dirección de Chicago."
            if "explore" in data and "subtitle" in data["explore"]:
                data["explore"]["subtitle"] = "Explorar parcelas por área comunitaria y clase de propiedad."

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

process_all()
print("UX polish complete")
