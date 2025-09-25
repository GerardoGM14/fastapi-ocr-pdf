#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional

import requests
from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXT = ".pdf"

def is_image(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXTS

def to_pdf_bytes_from_image(image_path: Path) -> bytes:
    with Image.open(image_path) as im:
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PDF", resolution=300.0)
        return buf.getvalue()

def read_pdf_bytes(pdf_path: Path) -> bytes:
    return pdf_path.read_bytes()

def build_range_paths(template: str, start: int, end: int) -> List[Path]:
    # template con {num} o {num:04d}
    return [Path(template.format(num=n)) for n in range(start, end + 1)]

def glob_paths(base_dir: Path, pattern: str) -> List[Path]:
    return sorted(base_dir.glob(pattern))

def ensure_outdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def post_extract(api_url: str, pdf_bytes: bytes, filename: str, timeout: int = 60) -> dict:
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    r = requests.post(api_url, files=files, timeout=timeout)
    r.raise_for_status()
    return r.json()

def process_one(path: Path, api_url: str, out_dir: Path, timeout: int) -> Tuple[Path, Optional[dict], Optional[str]]:
    try:
        if not path.exists():
            return (path, None, "No existe el archivo")

        if is_image(path):
            payload = to_pdf_bytes_from_image(path)
            send_name = path.with_suffix(".pdf").name
        elif path.suffix.lower() == PDF_EXT:
            payload = read_pdf_bytes(path)
            send_name = path.name
        else:
            return (path, None, f"Extensión no soportada: {path.suffix}")

        data = post_extract(api_url, payload, send_name, timeout=timeout)

        # Normaliza: si la API devolviera lista, toma el primero
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return (path, None, "Respuesta inesperada del API")

        ensure_outdir(out_dir)
        out_file = out_dir / f"{path.stem}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Log breve
        ensayo = data.get("informe", {}).get("numero_ensayo", "")
        elems = len(data.get("informe_elemento") or [])
        print(f"[OK] {path.name} → ensayo {ensayo}, elementos={elems}")
        return (path, data, None)

    except Exception as e:
        return (path, None, str(e))

def main():
    ap = argparse.ArgumentParser(description="Llama a la API /extract para una lista de imágenes/PDF y guarda el JSON.")
    ap.add_argument("--api-url", default="http://localhost:8000/extract", help="URL del endpoint /extract")
    # Modos de entrada (usa uno u otro)
    ap.add_argument("--range-template", help='Template con {num} o {num:04d}, ej: "C:/data/IMG_{num:04d}.jpg"')
    ap.add_argument("--start", type=int, help="Inicio del rango (incl.)")
    ap.add_argument("--end", type=int, help="Fin del rango (incl.)")
    ap.add_argument("--dir", help="Carpeta base para buscar archivos")
    ap.add_argument("--pattern", default="*.pdf", help='Patrón glob, ej: "*.pdf" o "*.png"')
    # Salidas
    ap.add_argument("--out-dir", default="./out_json", help="Directorio donde guardar los JSON")
    ap.add_argument("--timeout", type=int, default=90, help="Timeout por request (seg.)")
    args = ap.parse_args()

    # Construir lista de archivos
    if args.range_template and args.start is not None and args.end is not None:
        files = build_range_paths(args.range_template, args.start, args.end)
    else:
        base = Path(args.dir or ".")
        files = glob_paths(base, args.pattern)

    if not files:
        print("No se encontraron archivos a procesar. Revisa --range-template/--start/--end o --dir/--pattern.", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out_dir)
    ok, fail = 0, 0
    for p in files:
        _, data, err = process_one(p, args.api_url, out_dir, args.timeout)
        if err or not data:
            print(f"[ERROR] {p.name}: {err}", file=sys.stderr)
            fail += 1
        else:
            ok += 1

    print(f"\nResumen: {ok} OK, {fail} con error. JSONs en: {out_dir.resolve()}")

if __name__ == "__main__":
    main()
