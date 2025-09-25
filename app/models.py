from pydantic import BaseModel, Field
from typing import List, Optional

class Informe(BaseModel):
    numero_ensayo: str
    cliente: str
    fecha_recepcion: str  # ISO yyyy-mm-dd
    fecha_inicio: str
    fecha_termino: str

class InformeElemento(BaseModel):
    numero_ensayo: str
    elemento: str   # Au, Ag, Cu, Pb, Zn, As, H2O
    nombre: str     # Oro, Plata, ...
    unidad: str     # g/tm o %
    ley: float

class ExtractResponse(BaseModel):
    informe: Informe
    informe_elemento: List[InformeElemento]
