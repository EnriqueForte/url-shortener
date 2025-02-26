import csv
import os
import random
import string
import datetime
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Inicializar la aplicación Flask
app = Flask(__name__)
app.config.from_object(Config)

# Inicializar la base de datos
db = SQLAlchemy(app)
print(f"Usando base de datos en: {app.config['SQLALCHEMY_DATABASE_URI']}")

# Modelo de la base de datos para las URLs
class Url(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500), nullable=False)
    short_code = db.Column(db.String(6), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    access_count = db.Column(db.Integer, default=0)

# Funcion para generar un código corto único
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(characters, k=length))        # Verificar unicidad
        if not Url.query.filter_by(short_code=code).first():
            return code
        
# Crear la bbdd si no existe
with app.app_context():
    db.create_all()

# Ruta para la ineterfaz de usuario
@app.route('/')
def index():
    return render_template('index.html')

# Endpoint para crear la URL corta (POST/shorten)
@app.route('/shorten', methods=['POST'])
def shorten():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    
    original_url = data['url']
    # Validar que sea un URL válida (básico)
    if not original_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL'}), 400
    
    # Crear nueva entrada en la bbdd
    short_code = generate_short_code()
    new_url = Url(original_url=original_url, short_code=short_code)
    db.session.add(new_url)
    db.session.commit()
    print(f"Guardado: ID={new_url.id}, ShortCode={new_url.short_code}, URL={new_url.original_url}, ") #Confirmamos que se ha guardado

    # Respuesta con la URL creada
    response = {
        'id': new_url.id,
        'url' : new_url.original_url,
        'shortCode': f"{app.config['BASE_URL'].rstrip('/')}/{new_url.short_code}",
        'createdAt' : new_url.created_at.isoformat() + 'Z',
        'updatedAt' : new_url.updated_at.isoformat() + 'Z',

    }
    return jsonify(response), 201

# Endpoint para redirigir a la URL original (GET/<short_code>)
@app.route('/shorten/<short_code>', methods=['GET'])
def get_url(short_code):
    url = Url.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404

    # Incrementar el contador de accesos
    url.access_count += 1
    db.session.commit()

    # Redirigir a la URL original
    return redirect(url.original_url, code=302)

# Endpoint para actualizar una URL corta (PUT/shorten/<short_code>)
@app.route('/shorten/<short_code>', methods=['PUT'])
def update_url(short_code):
    url = Url.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    new_url = data['url'] 
    if not new_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Invalid URL format'}), 400

    # Actualizar la URL
    url.original_url = new_url
    db.session.commit()
    
    # Respuesta con la URL actualizada
    response = {
        'id': url.id,
        'url' : url.original_url,
        'shortCode' : f"{app.config['BASE_URL'].rstrip('/')}/{url.short_code}",
        'createdAt' : url.created_at.isoformat() + 'Z',
        'updatedAt' : url.updated_at.isoformat() + 'Z',
    }
    return jsonify(response), 200

# Endpoint para eliminar una URL corta (DELETE/shorten/<short_code>)
@app.route('/shorten/<short_code>', methods=['DELETE'])
def delete_url(short_code):
    url = Url.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    # Eliminar la URL
    db.session.delete(url)
    db.session.commit()
    return '', 204

# Endpoint para obtener las estadísticas de una URL corta (GET/shorten/<short_code>/stats)
@app.route('/shorten/<short_code>/stats', methods=['GET'])
def get_stats(short_code):
    url = Url.query.filter_by(short_code=short_code).first()
    if not url:
        return jsonify({'error': 'Short URL not found'}), 404
    
    # Respuesta con las estadísticas
    response = {
        'id': url.id,
        'url' : url.original_url,
        'shortCode' : f"{app.config['BASE_URL'].rstrip('/')}/{url.short_code}",
        'createdAt' : url.created_at.isoformat() + 'Z',
        'updatedAt' : url.updated_at.isoformat() + 'Z',
        'accessCount' : url.access_count
    }
    return jsonify(response), 200

# Endpoint para obtener todas las URLs cortas (GET/shorten)
@app.route('/db', methods=['GET'])
def view_database():
    urls = Url.query.all()
    data = [{
        'id': url.id,
        'shortCode': url.short_code,
        'url': url.original_url,
        'accessCount': url.access_count,
        'created_at': url.created_at.isoformat() + 'Z',
        'updated_at': url.updated_at.isoformat() + 'Z'
    } for url in urls]
    return jsonify(data), 200

# Endpoint para exportar todas las URLs cortas a un archivo CSV (GET/export_csv)
@app.route('/export_csv', methods=['GET'])
def export_csv():
    urls = Url.query.all()
    export_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'exports')
    os.makedirs(export_dir, exist_ok=True)  # Crea la carpeta 'exports' si no existe
    csv_path = os.path.join(export_dir, 'urls.csv')

    # Escribir los datos en el archivo CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Short Code', 'URL', 'Access Count'])
        for url in urls:
            writer.writerow([url.id, url.short_code, url.original_url, url.access_count])

    # Enviar el archivo al usuario como descarga
    return send_file(csv_path, as_attachment=True, download_name='urls.csv')

# Ejecutar la aplicación
if __name__ == '__main__':
    app.run(debug=True)

   