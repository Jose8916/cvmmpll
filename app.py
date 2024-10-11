from flask import Flask, request, render_template, redirect, url_for, session, flash, make_response
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
import smtplib
import random
import os
from dotenv import load_dotenv, set_key
from email.mime.text import MIMEText

app = Flask(__name__)

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        options='-c client_encoding=UTF8'
    )
    return conn

@app.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response

@app.route('/', methods=['GET', 'POST'])
def search():
    data = {
        "document_type": "DNI",
        "dni": "",
        "nombres_apellidos": "",
        "licencia": "",
        "fecha_revalidacion": "",
        "categoria": "",
        "mensaje": ""
    }

    if request.method == 'POST':
        document_type = request.form['document_type']
        dni = request.form['dni']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute('SELECT dni, nombres, apellidos, licencia, fecha_revalidacion, categoria FROM tabla_consulta_pallasca WHERE dni = %s', (dni,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            fecha_revalidacion = result['fecha_revalidacion'].strftime('%d-%m-%Y') if result['fecha_revalidacion'] else ''
            data = {
                "document_type": document_type,
                "dni": result['dni'],
                "nombres_apellidos": f"{result['nombres']} {result['apellidos']}",
                "licencia": result['licencia'],
                "fecha_revalidacion": fecha_revalidacion,
                "categoria": result['categoria'],
                "mensaje": ""
            }
        else:
            data["mensaje"] = f"{document_type} no registrado"

    return render_template('search.html', data=data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        dni = request.form['dni']
        password = request.form['password']

        if dni == 'admin' and password == read_password():
            session['logged_in'] = True
            return redirect(url_for('manejodatos'))
        else:
            flash('Credenciales incorrectas, intente de nuevo.', 'danger')
            print('Credenciales incorrectas, intente de nuevo.')
    return render_template('login.html')

# Lee la clave de admin desde las variables de entorno
def read_password():
    return os.getenv('ADMIN_PASSWORD')  # clave por defecto

# Escribe la nueva clave de admin en las variables de entorno
def write_password(new_password):
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    set_key(dotenv_path, 'ADMIN_PASSWORD', new_password)
    load_dotenv(dotenv_path)  # Recargar las variables de entorno

# funct para enviar el correo con la clave de verificacion
def send_verification_email(email, code):
    msg = MIMEText(f'Su codigo de verificacion es: {code}')
    msg['Subject'] = 'Codigo de Verificacion'
    msg['From'] = 'desarrolladorpallasca@gmail.com'
    msg['To'] = email

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('desarrolladorpallasca@gmail.com', 'rnsz dxrg xfel svhn')
        server.send_message(msg)

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    verification_code = ''.join(random.choices('0123456789', k=7))
    session['verification_code'] = verification_code
    send_verification_email('desarrolladorpallasca@gmail.com', verification_code)
    flash('Se ha enviado una clave de 7 caracteres de numeros al correo desarrolladorpallasca@gmail.com.', 'info')
    print('Se ha enviado una clave de 7 caracteres de numeros al correo desarrolladorpallasca@gmail.com.', 'info')
    return redirect(url_for('verify_code'))

# Ruta para mostrar el formulario de verificacion de la clave
@app.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    if request.method == 'POST':
        entered_code = request.form['verification_code']
        if entered_code == session.get('verification_code'):
            session.pop('verification_code', None)
            return redirect(url_for('change_password'))
        else:
            flash('la clave incorrecto, intente de nuevo.', 'danger')
            print('la clave incorrecto, intente de nuevo.', 'danger')
    return render_template('verify_code.html')

# Ruta para mostrar el formulario de cambio de clave
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password == confirm_password:
            write_password(new_password)  # Escribe la nueva clave en .env
            flash('clave cambiada de forma exitosa.', 'success')
            print('clave cambiada de forma exitosa.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Las claves no coinciden, intente de nuevo.', 'danger')
            print('Las claves no coinciden, intente de nuevo.', 'danger')
    return render_template('change_password.html')

@app.route('/manejodatos')
def manejodatos():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM tabla_consulta_pallasca ORDER BY dni LIMIT %s OFFSET %s', (per_page, offset))
    data = cur.fetchall()
    cur.execute('SELECT COUNT(*) FROM tabla_consulta_pallasca')
    total = cur.fetchone()[0]
    cur.close()
    conn.close()

    return render_template('manejodatos.html', data=data, page=page, per_page=per_page, total=total)

@app.route('/add_data', methods=['POST'])
def add_data():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        dni = request.form['dni']
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        licencia = request.form['licencia']
        fecha_revalidacion = request.form['fecha_revalidacion']
        categoria = request.form['categoria']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO tabla_consulta_pallasca (dni, nombres, apellidos, licencia, fecha_revalidacion, categoria) VALUES (%s, %s, %s, %s, %s, %s)',
                    (dni, nombres, apellidos, licencia, fecha_revalidacion, categoria))
        conn.commit()
        cur.close()
        conn.close()
        flash('Datos ingresados correctamente.', 'success')
        print('Datos ingresados correctamente.', 'success')
    except Exception as e:
        flash(f'Error al ingresar los datos: {str(e)}', 'danger')
        print(f'Error al ingresar los datos: {str(e)}', 'danger')

    return redirect(url_for('manejodatos'))

@app.route('/edit_data', methods=['POST'])
def edit_data():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        original_dni = request.form['originalDni']  # DNI original
        new_dni = request.form['dni']  # Nuevo DNI (puede ser el mismo o modificado)
        nombres = request.form['nombres']
        apellidos = request.form['apellidos']
        licencia = request.form['licencia']
        fecha_revalidacion = request.form['fecha_revalidacion']
        categoria = request.form['categoria']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE tabla_consulta_pallasca SET dni=%s, nombres=%s, apellidos=%s, licencia=%s, fecha_revalidacion=%s, categoria=%s WHERE dni=%s',
                    (new_dni, nombres, apellidos, licencia, fecha_revalidacion, categoria, original_dni))
        conn.commit()
        cur.close()
        conn.close()
        flash('Datos actualizados correctamente.', 'success')
        print('Datos actualizados correctamente.', 'success')
    except Exception as e:
        flash(f'Error al actualizar los datos: {str(e)}', 'danger')
        print(f'Error al actualizar los datos: {str(e)}', 'danger')

    return redirect(url_for('manejodatos'))

def parse_fecha(fecha):
    if isinstance(fecha, datetime):
        # Si la fecha es de tipo datetime, extraemos solo la parte de la fecha
        return fecha.date()
    elif isinstance(fecha, str):
        for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(fecha, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Formato de fecha no válido: {fecha}")


@app.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.xls') or file.filename.endswith('.xlsx'):
            try:
                df = pd.read_excel(file)
                conn = get_db_connection()
                cur = conn.cursor()
                for index, row in df.iterrows():
                    try:
                        fecha_revalidacion = parse_fecha(row['fecha_revalidacion'])
                    except ValueError as e:
                        flash(f'Error en la fila {index + 1}: {e}', 'danger')
                        print(f'Error en la fila {index + 1}: {e}')
                        continue

                    cur.execute('INSERT INTO tabla_consulta_pallasca (dni, nombres, apellidos, licencia, fecha_revalidacion, categoria) VALUES (%s, %s, %s, %s, %s, %s)',
                                (row['nro_documento'], row['NOMBRES'], row['APELLIDOS'], row['LICENCIA'], fecha_revalidacion, row['categoria']))
                conn.commit()
                cur.close()
                conn.close()
                flash('Datos cargados desde el archivo Excel correctamente.', 'success')
                print('Datos cargados desde el archivo Excel correctamente.', 'success')
            except Exception as e:
                flash(f'Error al procesar el archivo: {str(e)}', 'danger')
                print(f'Error al procesar el archivo: {str(e)}', 'danger')
        else:
            flash('Formato de archivo no soportado. Por favor, sube un archivo Excel.', 'danger')
            print('Formato de archivo no soportado. Por favor, sube un archivo Excel.', 'danger')
        return redirect(url_for('manejodatos'))
    return render_template('upload_excel.html')


@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.csv'):
            try:
                df = pd.read_csv(file)
                conn = get_db_connection()
                cur = conn.cursor()
                for index, row in df.iterrows():
                    try:
                        fecha_revalidacion = datetime.strptime(str(row['fecha_revalidacion']), '%d-%m-%Y').date()
                    except ValueError:
                        flash(f'Error en la fila {index + 1}: Fecha de revalidacion no es correcta.', 'danger')
                        print(f'Error en la fila {index + 1}: Fecha de revalidacion no es correcta.', 'danger')
                        continue

                    cur.execute('INSERT INTO tabla_consulta_pallasca (dni, nombres, apellidos, licencia, fecha_revalidacion, categoria) VALUES (%s, %s, %s, %s, %s, %s)',
                                (row['dni'], row['nombres'], row['apellidos'], row['licencia'], fecha_revalidacion, row['categoria']))
                conn.commit()
                cur.close()
                conn.close()
                flash('Datos cargados desde el archivo CSV correctamente.', 'success')
                print('Datos cargados desde el archivo CSV correctamente.', 'success')
            except Exception as e:
                flash(f'Error al procesar el archivo: {str(e)}', 'danger')
                print(f'Error al procesar el archivo: {str(e)}', 'danger')
        else:
            flash('Formato de archivo no soportado. Por favor, sube un archivo CSV.', 'danger')
            print('Formato de archivo no soportado. Por favor, sube un archivo CSV.', 'danger')
        return redirect(url_for('manejodatos'))
    return render_template('upload_csv.html')

@app.route('/delete_data/<dni>', methods=['POST'])
def delete_data(dni):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM tabla_consulta_pallasca WHERE dni = %s', (dni,))
        conn.commit()
        cur.close()
        conn.close()
        flash('Registro eliminado correctamente.', 'success')
        print('Registro eliminado correctamente.')
    except Exception as e:
        flash(f'Error al eliminar el registro: {str(e)}', 'danger')
        print(f'Error al eliminar el registro: {str(e)}')

    return redirect(url_for('manejodatos'))

@app.route('/logout')
def logout():
    session['logged_in'] = False
    session.pop('logged_in', None)
    response = make_response(redirect(url_for('login')))
    response.cache_control.no_store = True
    return response

if __name__ == '__main__':
    app.run(debug=True)
