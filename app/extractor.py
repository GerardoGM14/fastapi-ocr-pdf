import pdfplumber, re
from typing import Dict, List, Tuple
from .utils import to_iso, try_float
from .mappers import normalize_element

RX_NUM = re.compile(r"INFORME DE ENSAYO\s*N[°º]\s*(\d+)", re.I)
RX_CLIENTE = re.compile(r"Cliente\s*:\s*(.+)", re.I)
RX_REC = re.compile(r"Fecha de Recepción\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
RX_INI = re.compile(r"Fecha de Inicio de Ensayo\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
RX_FIN = re.compile(r"Fecha de Término de Ensayo\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)

def extract_header(text: str) -> Dict:
    numero = RX_NUM.search(text)
    cliente = RX_CLIENTE.search(text)
    frec = RX_REC.search(text)
    fini = RX_INI.search(text)
    ffin = RX_FIN.search(text)

    return {
        "numero_ensayo": numero.group(1).strip() if numero else "",
        "cliente": (cliente.group(1).strip() if cliente else "").rstrip(" ."),
        "fecha_recepcion": to_iso(frec.group(1)) if frec else "",
        "fecha_inicio": to_iso(fini.group(1)) if fini else "",
        "fecha_termino": to_iso(ffin.group(1)) if ffin else "",
    }

def find_elem_table(page) -> Tuple[List[str], List[str]]:
    """
    Devuelve (headers_elementos, fila_ley_valores) a partir de una tabla
    cuya primera columna diga 'Elemento' y exista una fila 'Ley'.
    """
    tables = page.extract_tables()
    for t in tables:
        # buscamos cabecera con 'Elemento'
        header = None
        for row in t[:3]:
            if row and any("Elemento" in str(c) for c in row):
                header = row
                break
        if not header:
            continue

        # Identificar fila unidades (suele decir 'Unidad') y fila 'Ley'
        unidad_row = None
        ley_row = None
        for row in t:
            s0 = (row[0] or "").strip().lower()
            if "unidad" in s0:
                unidad_row = row
            if s0 == "ley":
                ley_row = row

        # Construimos columnas a partir de header: ignoramos la primera celda ('Elemento')
        if header and ley_row:
            # Extrae nombres de elementos desde header alineados
            elems = [c for c in header[1:] if c]
            # Valores ley alineados por columna (a partir de col 1)
            vals  = [c for c in ley_row[1:] if c]
            # Si hay fila de unidad, la tomamos; si no, inferimos
            units = [c for c in (unidad_row[1:] if unidad_row else [])]

            return (elems, units, vals)
    return ([], [], [])

def extract_elements_from_page(page, numero_ensayo: str):
    elems, units, vals = find_elem_table(page)
    results = []
    for i, label in enumerate(elems):
        sym, name = normalize_element(str(label))
        unit = (units[i] if i < len(units) else "").strip()
        ley  = try_float(vals[i]) if i < len(vals) else None
        if ley is None:
            continue
        results.append({
            "numero_ensayo": numero_ensayo,
            "elemento": sym,
            "nombre": name,
            "unidad": unit or infer_unit(sym),
            "ley": ley
        })
    return results

def infer_unit(sym: str) -> str:
    # Por defecto según laboratorio típico
    if sym in ("Au","Ag"):
        return "g/tm"
    return "%"

def extract_from_pdf(file_path: str):
    with pdfplumber.open(file_path) as pdf:
        # texto global para encabezado
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        header = extract_header(full_text)

        # elementos: buscamos en cada página hasta encontrar
        items = []
        for page in pdf.pages:
            items = extract_elements_from_page(page, header["numero_ensayo"])
            if items:
                break

    return {
        "informe": header,
        "informe_elemento": items
    }
