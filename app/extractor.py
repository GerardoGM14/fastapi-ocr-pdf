import pdfplumber, re
from typing import Dict, List, Tuple
from .utils import to_iso, try_float
from .mappers import normalize_element

# ------------------ Regex encabezado ------------------
RX_NUM = re.compile(r"INFORME DE ENSAYO\s*N[°º]\s*(\d+)", re.I)
RX_CLIENTE = re.compile(r"Cliente\s*:\s*(.+)", re.I)
RX_REC = re.compile(r"Fecha de Recepción\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
RX_INI = re.compile(r"Fecha de Inicio de Ensayo\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)
RX_FIN = re.compile(r"Fecha de Término de Ensayo\s*:\s*(\d{2}/\d{2}/\d{4})", re.I)

# ------------------ Fallback por texto ----------------
NUM_RX = re.compile(r'[-+]?\d+(?:[.,]\d+)?')

def _nums(s: str) -> List[float]:
    out: List[float] = []
    for m in NUM_RX.findall(s):
        v = try_float(m.replace(',', '.'))
        if v is not None:
            out.append(v)
    return out

def parse_elements_from_text_block(full_text: str, numero_ensayo: str) -> List[Dict]:
    """
    Maneja la 'tabla cruzada' típica incluso cuando:
    - 'Ley' no inicia la línea (va incrustada)
    - Los valores se cortan en más de una línea

    Orden esperado de la fila 'Ley':
      Au(g/tm), Au(ozt/tc), Ag(g/tm), Ag(ozt/tc), Cu, Pb, Zn, As, H2O
    De ahí tomamos: Au(g/tm), Ag(g/tm) y % para el resto.
    """
    lines = [ (raw or "").strip() for raw in full_text.splitlines() if (raw or "").strip() ]
    ley_vals: List[float] = []

    for i, line in enumerate(lines):
        # Aceptar si contiene " Ley " o empieza por Ley (tolerante a mayúsculas)
        if " Ley " in f" {line} " or line.lower().startswith("ley"):
            # Tomamos lo que viene luego de "Ley"
            tail = line.split("Ley", 1)[1] if "Ley" in line else line
            # Concatenamos hasta 2 líneas siguientes por si los números están cortados
            if i + 1 < len(lines):
                tail += " " + lines[i + 1]
            if i + 2 < len(lines):
                tail += " " + lines[i + 2]

            candidates = _nums(tail)
            if len(candidates) >= 7:
                ley_vals = candidates
                break

    if not ley_vals:
        return []

    # Mapeo de índices → (símbolo, nombre, unidad)
    mapping = [
        ("Au",  "Oro",      "g/tm", 0),  # Au g/tm
        ("Ag",  "Plata",    "g/tm", 2),  # Ag g/tm
        ("Cu",  "Cobre",    "%",    4),
        ("Pb",  "Plomo",    "%",    5),
        ("Zn",  "Zinc",     "%",    6),
        ("As",  "Arsénico", "%",    7),
        ("H2O", "Humedad",  "%",    8),
    ]

    out: List[Dict] = []
    for sym, name, unit, idx in mapping:
        if idx < len(ley_vals):
            out.append({
                "numero_ensayo": numero_ensayo,
                "elemento": sym,
                "nombre": name,
                "unidad": unit,
                "ley": ley_vals[idx]
            })
    return out

# ------------------ Encabezado ------------------
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

# ------------------ Intento tabla estructurada -------
def find_elem_table(page) -> Tuple[List[str], List[str], List[str]]:
    """
    Devuelve (elems_header, units_row, ley_row) si encuentra una tabla
    con primera columna 'Elemento' y una fila 'Ley'.
    """
    tables = page.extract_tables()
    for t in tables or []:
        header = None
        for row in t[:3]:
            if row and any("Elemento" in str(c) for c in row):
                header = row
                break
        if not header:
            continue

        unidad_row = None
        ley_row = None
        for row in t:
            s0 = (row[0] or "").strip().lower()
            if "unidad" in s0:
                unidad_row = row
            if s0 == "ley":
                ley_row = row

        if header and ley_row:
            elems = [c for c in header[1:] if c]
            vals  = [c for c in ley_row[1:] if c]
            units = [c for c in (unidad_row[1:] if unidad_row else [])]
            return (elems, units, vals)
    return ([], [], [])

def extract_elements_from_page(page, numero_ensayo: str) -> List[Dict]:
    elems, units, vals = find_elem_table(page)
    results: List[Dict] = []
    for i, label in enumerate(elems):
        sym, name = normalize_element(str(label))
        unit = (units[i] if i < len(units) else "")
        unit = (unit or "").strip()
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
    if sym in ("Au", "Ag"):
        return "g/tm"
    return "%"

# ------------------ Orquestador -----------------------
def extract_from_pdf(file_path: str):
    with pdfplumber.open(file_path) as pdf:
        full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        header = extract_header(full_text)

        # 1) Intento tabla
        items: List[Dict] = []
        for page in pdf.pages:
            items = extract_elements_from_page(page, header["numero_ensayo"])
            if items:
                break

        # 2) Fallback por texto si no hubo tabla o quedó vacío
        if not items:
            items = parse_elements_from_text_block(full_text, header["numero_ensayo"])

    # Asegura el punto final del cliente
    header["cliente"] = header["cliente"].rstrip()
    if header["cliente"] and not header["cliente"].endswith("."):
        header["cliente"] += "."

    return {
        "informe": header,
        "informe_elemento": items
    }
