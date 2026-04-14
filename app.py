from flask import Flask, render_template, request, make_response, redirect
from datetime import datetime
import sqlite3
import json
import pdfkit

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
            ventas_json TEXT
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


        data = {
            "precio_hora": precio_hora,
            "comision": comision
        }

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
    comision_porcentaje = settings["comision"]

    if request.method == 'POST':
        fecha = request.form.get('fecha')
        entrada = request.form.get('entrada')
        salida = request.form.get('salida')
        ventas_texto = request.form.get('ventas')

        # Calcular horas trabajadas
        formato = "%H:%M"
        h_entrada = datetime.strptime(entrada, formato)
        h_salida = datetime.strptime(salida, formato)
        horas = (h_salida - h_entrada).seconds / 3600

        salario = horas * precio_hora

        # Procesar ventas
        ventas = []
        total_ventas = 0
        total_comision = 0

        if ventas_texto.strip():
            lineas = ventas_texto.split("\n")
            for linea in lineas:
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

        reporte = {
            "fecha": fecha,
            "horas": horas,
            "salario": salario,
            "total_ventas": total_ventas,
            "total_comision": total_comision,
            "total_ganado": salario + total_comision,
            "ventas": ventas
        }

        # Guardar en historial
        conn = sqlite3.connect("historial.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO reportes (fecha, horas, salario, total_ventas, total_comision, total_ganado, ventas_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha,
            horas,
            salario,
            total_ventas,
            total_comision,
            salario + total_comision,
            json.dumps(ventas)
        ))
        conn.commit()
        conn.close()

        return render_template("index.html", reporte=reporte)

    return render_template("index.html", reporte=None)


# -----------------------------------
#   RUTA HISTORIAL
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
#   RUTA REPORTE PASADO
# -----------------------------------
@app.route('/reporte/<int:id>')
def reporte_pasado(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado, ventas_json FROM reportes WHERE id=?", (id,))
    fila = c.fetchone()
    conn.close()

    ventas = json.loads(fila[6])

    reporte = {
        "id": id,
        "fecha": fila[0],
        "horas": fila[1],
        "salario": fila[2],
        "total_ventas": fila[3],
        "total_comision": fila[4],
        "total_ganado": fila[5],
        "ventas": ventas
    }

    return render_template("reporte_pasado.html", reporte=reporte)


# -----------------------------------
#   CONFIG PDFKIT
# -----------------------------------
config = pdfkit.configuration(
    wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
)


# -----------------------------------
#   PDF DEL DÍA ACTUAL
# -----------------------------------
@app.route('/pdf', methods=['POST'])
def pdf():
    fecha = request.form.get('fecha')
    horas = request.form.get('horas')
    salario = request.form.get('salario')
    total_ventas = request.form.get('total_ventas')
    total_comision = request.form.get('total_comision')

    total_ganado = float(salario) + float(total_comision)

    html = render_template(
        "reporte_pdf.html",
        fecha=fecha,
        horas=horas,
        salario=salario,
        total_ventas=total_ventas,
        total_comision=total_comision,
        total_ganado=total_ganado,
        ventas=[]
    )

    pdf = pdfkit.from_string(html, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=reporte.pdf'

    return response


# -----------------------------------
#   PDF DE REPORTE GUARDADO
# -----------------------------------
@app.route('/pdf_reporte/<int:id>', methods=['POST'])
def pdf_reporte(id):
    conn = sqlite3.connect("historial.db")
    c = conn.cursor()
    c.execute("SELECT fecha, horas, salario, total_ventas, total_comision, total_ganado, ventas_json FROM reportes WHERE id=?", (id,))
    fila = c.fetchone()
    conn.close()

    ventas = json.loads(fila[6])

    html = render_template(
        "reporte_pdf.html",
        fecha=fila[0],
        horas=fila[1],
        salario=fila[2],
        total_ventas=fila[3],
        total_comision=fila[4],
        total_ganado=fila[5],
        ventas=ventas
    )

    pdf = pdfkit.from_string(html, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=reporte_{id}.pdf'

    return response


# -----------------------------------
#   INICIAR APP
# -----------------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True)
