from flask import Flask, render_template, request, make_response, redirect
from datetime import datetime
import sqlite3
import json
import platform

# -----------------------------------
#   DETECTAR SISTEMA OPERATIVO
# -----------------------------------
if platform.system() == "Windows":
    import pdfkit
    PDF_MODE = "pdfkit"
else:
    from weasyprint import HTML
    PDF_MODE = "weasyprint"

app = Flask(__name__)

# -----------------------------------
#   INICIALIZAR BASE DE DATOS
# -----------------------------------
def init_db():
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            horas REAL,
            salario REAL,
            total_ventas REAL,
            total_comision REAL,
            total_ganado REAL,
            ventas_json TEXT,
            personas INTEGER DEFAULT 1,
            companero TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

# -----------------------------------
#   CARGAR SETTINGS DESDE JSON
# -----------------------------------
def cargar_settings():
    try:
        with open("settings.json") as f:
            return json.load(f)
    except:
        return {"precio_hora": 17, "comision": 0.02}

# -----------------------------------
#   RUTA DE SETTINGS
# -----------------------------------
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        precio_hora = float(request.form.get('precio_hora'))
        comision = float(request.form.get('comision')) / 100

        data = {"precio_hora": precio_hora, "comision": comision}

        with open("settings.json", "w") as f:
            json.dump(data, f)

        return redirect('/')

    data = cargar_settings()
    return render_template("settings.html", settings=data)

# -----------------------------------
#   RUTA PRINCIPAL
# -----------------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    settings = cargar_settings()
    precio_hora = settings["precio_hora"]

    if request.method == 'POST':
        fecha = request.form.get('fecha')
        entrada = request.form.get('entrada')
        salida = request.form.get('salida')
        ventas_texto = request.form.get('ventas')

        personas = int(request.form.get('personas'))
        companero = request.form.get('companero') if personas == 2 else ""

        comision_porcentaje = settings["comision"] / personas

        formato = "%H:%M"
        h_entrada = datetime.strptime(entrada, formato)
        h_salida = datetime.strptime(salida, formato)
        horas = (h_salida - h_entrada).seconds / 3600

        salario = horas * precio_hora

        ventas = []
        total_ventas = 0
        total_comision = 0

        if ventas_texto.strip():
            for linea in ventas_texto.split("\n"):
                if "," in linea:
                    descripcion, precio = linea.split(",", 1)
                    precio = float(precio.strip())
                    comision = precio * comision_porcentaje

                    ventas.append({
                        "descripcion": descripcion.strip(),
                        "precio": precio,
                        "comision": comision
                    })

                    total_ventas += precio
                    total_comision += comision

        total_ganado = salario + total_comision

        conn = sqlite3.connect("historial.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO reportes (fecha, horas, salario, total_ventas, total_comision, total_ganado,
                                  ventas_json, personas, companero)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha, horas, salario, total_ventas, total_comision, total_ganado,
            json.dumps(ventas), personas, companero
        ))
        conn.commit()
        conn.close()

        reporte = {
            "fecha": fecha,
            "horas": horas,
            "salario": salario,
            "total_ventas": total_ventas,
            "total_comision": total_comision,
            "total_ganado": total_ganado,
            "ventas": ventas,
            "personas": personas,
            "companero": companero
        }

        return render_template("index.html", reporte=reporte)

    return render_template("index.html", reporte=None)

# -----------------------------------
#   HISTORIAL
# -----------------------------------
@app.route('/historial')
def historial():
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("SELECT id, fecha, total_ganado FROM reportes ORDER BY id DESC")
    datos = c.fetchall()
    conn.close()
    return render_template("historial.html", reportes=datos)

# -----------------------------------
#   REPORTE PASADO
# -----------------------------------
@app.route('/reporte/<int:id>')
def reporte_pasado(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("""
        SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado,
               ventas_json, personas, companero
        FROM reportes WHERE id=?
    """, (id,))
    fila = c.fetchone()
    conn.close()

    if not fila:
        return "Reporte no encontrado", 404

    ventas = json.loads(fila[6])

    reporte = {
        "id": id,
        "fecha": fila[0],
        "horas": fila[1],
        "salario": fila[2],
        "total_ventas": fila[3],
        "total_comision": fila[4],
        "total_ganado": fila[5],
        "ventas": ventas,
        "personas": fila[7],
        "companero": fila[8]
    }

    return render_template("reporte_pasado.html", reporte=reporte)

# -----------------------------------
#   EDITAR REPORTE
# -----------------------------------
@app.route('/editar/<int:id>')
def editar(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("""
        SELECT fecha, horas, salario, ventas_json, personas, companero
        FROM reportes WHERE id=?
    """, (id,))
    fila = c.fetchone()
    conn.close()

    if not fila:
        return "Reporte no encontrado", 404

    ventas = json.loads(fila[3])

    return render_template(
        "editar_reporte.html",
        id=id,
        fecha=fila[0],
        horas=fila[1],
        salario=fila[2],
        ventas=ventas,
        personas=fila[4],
        companero=fila[5]
    )

# -----------------------------------
#   ACTUALIZAR REPORTE
# -----------------------------------
@app.route('/actualizar/<int:id>', methods=['POST'])
def actualizar(id):
    fecha = request.form.get('fecha')
    horas = float(request.form.get('horas'))

    settings = cargar_settings()
    precio_hora = settings["precio_hora"]
    salario = horas * precio_hora

    personas = int(request.form.get('personas', 1))
    companero = request.form.get('companero') if personas == 2 else ""

    descripciones = request.form.getlist('descripcion[]')
    precios = request.form.getlist('precio[]')

    ventas = []
    total_ventas = 0
    total_comision = 0

    comision_porcentaje = settings["comision"] / personas

    for d, p in zip(descripciones, precios):
        if d.strip() and p.strip():
            precio = float(p)
            comision = precio * comision_porcentaje
            ventas.append({
                "descripcion": d.strip(),
                "precio": precio,
                "comision": comision
            })
            total_ventas += precio
            total_comision += comision

    total_ganado = salario + total_comision

    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("""
        UPDATE reportes
        SET fecha=?, horas=?, salario=?, total_ventas=?, total_comision=?, total_ganado=?,
            ventas_json=?, personas=?, companero=?
        WHERE id=?
    """, (
        fecha, horas, salario, total_ventas, total_comision, total_ganado,
        json.dumps(ventas), personas, companero, id
    ))
    conn.commit()
    conn.close()

    return redirect(f"/reporte/{id}")

# -----------------------------------
#   BORRAR REPORTE
# -----------------------------------
@app.route('/borrar/<int:id>', methods=['POST'])
def borrar(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("DELETE FROM reportes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/historial')

# -----------------------------------
#   PDF DEL DÍA
# -----------------------------------
@app.route('/pdf', methods=['POST'])
def pdf():
    fecha = request.form.get('fecha')
    horas = request.form.get('horas')
    salario = request.form.get('salario')
    total_ventas = request.form.get('total_ventas')
    total_comision = request.form.get('total_comision')
    personas = request.form.get('personas')
    companero = request.form.get('companero')

    total_ganado = float(salario) + float(total_comision)

    html = render_template(
        "reporte_pdf.html",
        fecha=fecha,
        horas=horas,
        salario=salario,
        total_ventas=total_ventas,
        total_comision=total_comision,
        total_ganado=total_ganado,
        ventas=[],
        personas=personas,
        companero=companero
    )

    if PDF_MODE == "pdfkit":
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        pdf = pdfkit.from_string(html, False, configuration=config)
    else:
        pdf = HTML(string=html).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=reporte.pdf'

    return response

# -----------------------------------
#   PDF REPORTE GUARDADO
# -----------------------------------
@app.route('/pdf_reporte/<int:id>')
def pdf_reporte(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("""
        SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado,
               ventas_json, personas, companero
        FROM reportes WHERE id=?
    """, (id,))
    fila = c.fetchone()
    conn.close()

    if not fila:
        return "Reporte no encontrado", 404

    ventas = json.loads(fila[6])

    html = render_template(
        "reporte_pdf.html",
        fecha=fila[0],
        horas=fila[1],
        salario=fila[2],
        total_ventas=fila[3],
        total_comision=fila[4],
        total_ganado=fila[5],
        ventas=ventas,
        personas=fila[7],
        companero=fila[8]
    )

    if PDF_MODE == "pdfkit":
        config = pdfkit.configuration(
            wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
        )
        pdf = pdfkit.from_string(html, False, configuration=config)
    else:
        pdf = HTML(string=html).write_pdf()

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_{id}.pdf'

    return response

# -----------------------------------
#   TIME SHEET RESULT (WEB)
# -----------------------------------
@app.route("/timesheet_result", methods=["POST"])
def timesheet_result():
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    conn = sqlite3.connect("historial.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado
        FROM reportes
        WHERE fecha BETWEEN ? AND ?
        ORDER BY fecha ASC
    """, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()

    def decimal_to_hhmm(decimal_hours):
        horas = int(decimal_hours)
        minutos = int(round((decimal_hours - horas) * 60))
        return f"{horas:02d}:{minutos:02d}"

    processed = []
    total_days = 0
    total_hours_dec = 0.0
    total_salary = 0.0
    total_sales = 0.0
    total_commission = 0.0
    total_total = 0.0

    for r in rows:
        fecha, horas_dec, salario, ventas, comision, total = r
        horas_hhmm = decimal_to_hhmm(horas_dec)

        processed.append((
            fecha,
            "",
            "",
            horas_hhmm,
            float(salario),
            float(ventas),
            float(comision),
            float(total)
        ))

        total_days += 1
        total_hours_dec += float(horas_dec)
        total_salary += float(salario)
        total_sales += float(ventas)
        total_commission += float(comision)
        total_total += float(total)

    total_hours = int(total_hours_dec)
    total_minutes = int(round((total_hours_dec - total_hours) * 60))
    total_hours_hhmm = f"{total_hours:02d}:{total_minutes:02d}"

    return render_template(
        "timesheet.html",
        datos=processed,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        total_hours_hhmm=total_hours_hhmm,
        total_salary=total_salary,
        total_sales=total_sales,
        total_commission=total_commission,
        total_total=total_total
    )

# -----------------------------------
#   TIME SHEET PDF
# -----------------------------------
@app.route("/timesheet_pdf")
def timesheet_pdf():
    start_date = request.args.get("start")
    end_date = request.args.get("end")

    conn = sqlite3.connect("historial.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado
        FROM reportes
        WHERE fecha BETWEEN ? AND ?
        ORDER BY fecha ASC
    """, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()

    def decimal_to_hhmm(decimal_hours):
        horas = int(decimal_hours)
        minutos = int(round((decimal_hours - horas) * 60))
        return f"{horas:02d}:{minutos:02d}"

    processed = []
    total_days = 0
    total_hours_dec = 0.0
    total_salary = 0.0
    total_sales = 0.0
    total_commission = 0.0
    total_total = 0.0

    for r in rows:
        fecha, horas_dec, salario, ventas, comision, total = r
        horas_hhmm = decimal_to_hhmm(horas_dec)

        processed.append((
            fecha,
            "",
            "",
            horas_hhmm,
            float(salario),
            float(ventas),
            float(comision),
            float(total)
        ))

        total_days += 1
        total_hours_dec += float(horas_dec)
        total_salary += float(salario)
        total_sales += float(ventas)
        total_commission += float(comision)
        total_total += float(total)

    total_hours = int(total_hours_dec)
    total_minutes = int(round((total_hours_dec - total_hours) * 60))
    total_hours_hhmm = f"{total_hours:02d}:{total_minutes:02d}"

    return render_template(
        "timesheet_pdf.html",
        datos=processed,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        total_hours_hhmm=total_hours_hhmm,
        total_salary=total_salary,
        total_sales=total_sales,
        total_commission=total_commission,
        total_total=total_total
    )

# -----------------------------------
#   TIME SHEET FORM
# -----------------------------------
@app.route("/timesheet")
def timesheet():
    return render_template("timesheet_form.html")

# -----------------------------------
#   INICIAR APP
# -----------------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True)
