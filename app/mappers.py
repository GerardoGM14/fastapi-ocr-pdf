ELEMENTS = {
    "oro":  ("Au", "Oro"),
    "plata":("Ag", "Plata"),
    "cobre":("Cu", "Cobre"),
    "plomo":("Pb", "Plomo"),
    "zinc": ("Zn", "Zinc"),
    "arsénico":("As","Arsénico"),
    "arsenico":("As","Arsénico"),
    "humedad":("H2O","Humedad"),
}

def normalize_element(label: str):
    k = label.strip().lower().replace("(au)","").replace("(ag)","")\
         .replace("(cu)","").replace("(pb)","").replace("(zn)","")\
         .replace("(as)","").replace("(h2o)","").strip()
    for key,(sym,name) in ELEMENTS.items():
        if key in k:
            return sym, name
    # si no matchea, devolvemos etiqueta cruda
    return label.strip(), label.strip().title()
