from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from .models import ExtractResponse, Informe, InformeElemento
from .extractor import extract_from_pdf
import tempfile, shutil, os

app = FastAPI(title="PDF → JSON (Lab Ensayo)")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        data = extract_from_pdf(tmp_path)
        # Validación Pydantic
        return ExtractResponse(
            informe=Informe(**data["informe"]),
            informe_elemento=[InformeElemento(**r) for r in data["informe_elemento"]]
        )
    finally:
        os.remove(tmp_path)

# Opcional: carga masiva (varios PDFs en un zip)
@app.post("/extract/bulk")
async def extract_bulk(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(f.file, tmp)
            tmp_path = tmp.name
        try:
            out.append(extract_from_pdf(tmp_path))
        finally:
            os.remove(tmp_path)
    return JSONResponse(out)
