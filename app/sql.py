import os, json, pyodbc
from dotenv import load_dotenv
load_dotenv()

def get_conn():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={os.getenv('MSSQL_SERVER')};"
        f"DATABASE={os.getenv('MSSQL_DB')};"
        f"UID={os.getenv('MSSQL_USER')};PWD={os.getenv('MSSQL_PASS')}"
    )

def upsert_payload(payload: dict):
    conn = get_conn()
    cur = conn.cursor()

    inf = payload["informe"]
    cur.execute("""
        MERGE dbo.informe AS t
        USING (SELECT ? AS numero_ensayo) AS s
        ON (t.numero_ensayo = s.numero_ensayo)
        WHEN MATCHED THEN UPDATE SET
            cliente=?, fecha_recepcion=?, fecha_inicio=?, fecha_termino=?
        WHEN NOT MATCHED THEN INSERT(numero_ensayo,cliente,fecha_recepcion,fecha_inicio,fecha_termino)
        VALUES(?,?,?,?,?);
    """, inf["numero_ensayo"], inf["cliente"], inf["fecha_recepcion"], inf["fecha_inicio"], inf["fecha_termino"],
         inf["numero_ensayo"], inf["cliente"], inf["fecha_recepcion"], inf["fecha_inicio"], inf["fecha_termino"])

    # elementos
    cur.execute("DELETE FROM dbo.informe_elemento WHERE numero_ensayo = ?", inf["numero_ensayo"])
    for r in payload["informe_elemento"]:
        cur.execute("""
            INSERT INTO dbo.informe_elemento(numero_ensayo,elemento,nombre,unidad,ley)
            VALUES (?,?,?,?,?)
        """, r["numero_ensayo"], r["elemento"], r["nombre"], r["unidad"], r["ley"])

    conn.commit()
    cur.close()
    conn.close()
