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
    
    # Define exact substring replacements
    replacements = [
        # Inconsistent terminology
        ("tasación", "avalúo"),
        ("Tasación", "Avalúo"),
        ("tasado", "de avalúo"),
        ("Tasado", "De avalúo"),
        ("Tasados", "De avalúo"),
        ("tasados", "de avalúo"),
        ("parcela", "propiedad"),
        ("Parcela", "Propiedad"),
        
        # Auditoria de compra normalization
        ("Auditoría de Compra (Due Diligence)", "Auditoría de compra"),
        ("Auditoría de compra (due diligence)", "Auditoría de compra"),
        ("due diligence", "auditoría de compra"),
        
        # PTAXSIM normalization
        ("PTAXSIM", "PTAXSIM"), # Make sure it's consistent if needed
        
        # "Walk / Transit / Bike Score" spacing and format
        ("Walk / Transit / Bike Score", "Walk Score, Transit Score y Bike Score"),
        ("Walk Score®", "Walk Score"),
        
        # Fragments
        ("Una consulta. Veinticinco fuentes de datos.", "Una sola consulta. Veinticinco fuentes."),
        ("De la consulta al informe", "Del análisis al informe"),
        ("Consulte en español: sin lenguajes de consulta, sin configurar filtros y sin llenar formularios.", "Consulte en español. Sin consultas complejas, sin formularios.")
    ]

    for filename in os.listdir(base_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Apply global replacements
        replace_in_dict(data, replacements)
        
        # Apply specific overrides for landing.json
        if filename == "landing.json":
            if "valueProps" in data:
                data["valueProps"]["buildTitle"] = "Qué puede construir"
                data["valueProps"]["worthTitle"] = "Cuánto vale"
                data["valueProps"]["watchTitle"] = "Qué riesgos debe considerar"
                
                # Smooth the bodies a bit
                if "buildBody" in data["valueProps"]:
                    data["valueProps"]["buildBody"] = data["valueProps"]["buildBody"].replace("Sepa qué puede construir.", "")
                if "worthBody" in data["valueProps"]:
                    data["valueProps"]["worthBody"] = data["valueProps"]["worthBody"].replace("Sepa cuánto vale.", "")
                if "watchBody" in data["valueProps"]:
                    data["valueProps"]["watchBody"] = data["valueProps"]["watchBody"].replace("Sepa qué riesgos vigilar.", "")
                    
            if "story" in data:
                if "reportTitle" in data["story"]:
                    data["story"]["reportTitle"] = "Del análisis al informe"
                    
            if "howItWorks" in data:
                if "steps" in data["howItWorks"] and len(data["howItWorks"]["steps"]) > 0:
                    data["howItWorks"]["steps"][0]["description"] = "Consulte en español. Sin consultas complejas, sin formularios."
                    
            # Check "Una sola consulta"
            if "intelligence" in data and "heading" in data["intelligence"]:
                data["intelligence"]["heading"] = "Una sola consulta. Veinticinco fuentes."
                
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

process_all()
print("Polish complete")
