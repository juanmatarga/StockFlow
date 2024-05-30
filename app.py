from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, g
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import csv

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Necesario para utilizar flash messages


# Función para obtener la conexión a la base de datos
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('inventario.db')
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# Crear tabla de ventas
def create_sales_table():
    db = get_db()
    c = db.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_orden INTEGER,
        cliente TEXT,
        producto_id INTEGER,
        producto_nombre TEXT,
        cantidad INTEGER,
        precio_venta REAL,
        subtotal REAL,
        descuento REAL,
        cargo_envio REAL,
        total REAL
    )
    ''')
    db.commit()


# Crear tabla de productos si no existe y agregar columna unidad_medida si es necesario
def add_unidad_medida_column():
    db = get_db()
    c = db.cursor()

    # Verificar si la columna unidad_medida ya existe
    c.execute("PRAGMA table_info(productos)")
    columns = [col[1] for col in c.fetchall()]

    if 'unidad_medida' not in columns:
        # Si no existe, agregar la columna
        c.execute("ALTER TABLE productos ADD COLUMN unidad_medida TEXT DEFAULT 'unidades'")
        db.commit()


with app.app_context():
    add_unidad_medida_column()
    create_sales_table()


# Operaciones CRUD
def add_producto(nombre, cantidad, precio, unidad_medida):
    db = get_db()
    c = db.cursor()
    c.execute("INSERT INTO productos (nombre, cantidad, precio, unidad_medida) VALUES (?, ?, ?, ?)",
              (nombre, cantidad, precio, unidad_medida))
    db.commit()


def update_producto(id, nombre, cantidad, precio, unidad_medida):
    db = get_db()
    c = db.cursor()
    c.execute("UPDATE productos SET nombre = ?, cantidad = ?, precio = ?, unidad_medida = ? WHERE id = ?",
              (nombre, cantidad, precio, unidad_medida, id))
    db.commit()


def delete_producto(id):
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM productos WHERE id = ?", (id,))
    db.commit()


def get_productos():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM productos")
    rows = c.fetchall()
    productos = [dict(row) for row in rows]
    return productos


def get_producto(id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM productos WHERE id = ?", (id,))
    row = c.fetchone()
    if row:
        return dict(row)
    return None


# Rutas para la API
@app.route('/api/productos', methods=['GET'])
def get_productos_endpoint():
    productos = get_productos()
    return jsonify(productos)


@app.route('/api/productos', methods=['POST'])
def add_producto_endpoint():
    data = request.json
    if 'nombre' not in data or 'cantidad' not in data or 'precio' not in data or 'unidad_medida' not in data:
        return jsonify({'error': 'Datos incompletos'}), 400
    add_producto(data['nombre'], data['cantidad'], data['precio'], data['unidad_medida'])
    return jsonify({'message': 'Producto añadido'}), 201


@app.route('/api/productos/<int:id>', methods=['PUT'])
def update_producto_endpoint(id):
    data = request.json
    if 'nombre' not in data or 'cantidad' not in data or 'precio' not in data or 'unidad_medida' not in data:
        return jsonify({'error': 'Datos incompletos'}), 400
    update_producto(id, data['nombre'], data['cantidad'], data['precio'], data['unidad_medida'])
    return jsonify({'message': 'Producto actualizado'})


@app.route('/api/productos/<int:id>', methods=['DELETE'])
def delete_producto_endpoint(id):
    delete_producto(id)
    return jsonify({'message': 'Producto eliminado'})


@app.route('/api/analitica', methods=['GET'])
def analitica():
    productos = get_productos()
    
    df = pd.DataFrame(productos, columns=['id', 'nombre', 'cantidad', 'precio', 'unidad_medida'])
    
    df.to_csv('inventario.csv', index=False)
    
    df = pd.read_csv('inventario.csv')
    
    analisis = df.describe().to_json()
    df['nombre'] = df['nombre'].astype(str) + ' (' + df['unidad_medida'] + ')'
    print(df[['nombre', 'cantidad']])
    df.plot(kind='bar', x='nombre', y='cantidad')
    plt.savefig('inventario.png')
    plt.close()
    
    return jsonify(analisis)

@app.route('/api/productos/carga_venta', methods=['GET', 'POST'])
def carga_venta():
    if request.method == 'POST':
        cliente = request.form['cliente']
        producto_id = int(request.form['producto'])
        cantidad = int(request.form['cantidad'])
        precio_venta = float(request.form['precio_venta'])
        descuento = float(request.form['descuento'])
        cargo_envio = float(request.form['cargo_envio'])

        producto = get_producto(producto_id)
        if producto and cantidad <= producto['cantidad']:
            subtotal = cantidad * precio_venta
            total = subtotal - descuento + cargo_envio

            db = get_db()
            c = db.cursor()
            c.execute("SELECT MAX(numero_orden) FROM ventas")
            max_orden = c.fetchone()[0]
            numero_orden = (max_orden if max_orden else 0) + 1

            c.execute('''
                INSERT INTO ventas (numero_orden, cliente, producto_id, producto_nombre, cantidad, precio_venta, subtotal, descuento, cargo_envio, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (numero_orden, cliente, producto_id, producto['nombre'], cantidad, precio_venta, subtotal, descuento,
                  cargo_envio, total))

            c.execute("UPDATE productos SET cantidad = cantidad - ? WHERE id = ?", (cantidad, producto_id))

            db.commit()

            # Guardar la venta en un archivo CSV
            venta = {
                'numero_orden': numero_orden,
                'cliente': cliente,
                'producto_id': producto_id,
                'producto_nombre': producto['nombre'],
                'cantidad': cantidad,
                'precio_venta': precio_venta,
                'subtotal': subtotal,
                'descuento': descuento,
                'cargo_envio': cargo_envio,
                'total': total
            }
            ventas_csv_path = 'ventas.csv'
            file_exists = os.path.isfile(ventas_csv_path)
            with open(ventas_csv_path, 'a', newline='') as csvfile:
                fieldnames = ['numero_orden', 'cliente', 'producto_id', 'producto_nombre', 'cantidad', 'precio_venta',
                              'subtotal', 'descuento', 'cargo_envio', 'total']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(venta)

            flash('Orden de venta cargada exitosamente', 'success')
            return redirect(url_for('carga_venta'))

    productos = get_productos()
    ventas = []
    ventas_csv_path = 'ventas.csv'
    if os.path.isfile(ventas_csv_path):
        with open(ventas_csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row['numero_orden'] = int(row['numero_orden'])
                row['cantidad'] = int(row['cantidad'])
                row['precio_venta'] = float(row['precio_venta'])
                row['subtotal'] = float(row['subtotal'])
                row['descuento'] = float(row['descuento'])
                row['cargo_envio'] = float(row['cargo_envio'])
                row['total'] = float(row['total'])
                ventas.append(row)

    return render_template('carga_venta.html', productos=productos, ventas=ventas)

# Rutas para la interfaz web
@app.route('/')
def index():
    productos = get_productos()
    return render_template('index.html', productos=productos)

@app.route('/api/ventas', methods=['GET'])
def get_ventas_endpoint():
    ventas = []
    ventas_csv_path = 'ventas.csv'
    if os.path.isfile(ventas_csv_path):
        with open(ventas_csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                row['numero_orden'] = int(row['numero_orden'])
                row['cantidad'] = int(row['cantidad'])
                row['precio_venta'] = float(row['precio_venta'])
                row['subtotal'] = float(row['subtotal'])
                row['descuento'] = float(row['descuento'])
                row['cargo_envio'] = float(row['cargo_envio'])
                row['total'] = float(row['total'])
                ventas.append(row)
    return jsonify(ventas)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        nombre = request.form['nombre']
        cantidad = request.form['cantidad']
        precio = request.form['precio']
        unidad_medida = request.form['unidad_medida']
        add_producto(nombre, cantidad, precio, unidad_medida)
        flash('Producto añadido exitosamente', 'success')
        return redirect(url_for('index'))
    return render_template('add_product.html')


@app.route('/edit_product/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    producto = get_producto(id)
    if request.method == 'POST':
        nombre = request.form['nombre']
        cantidad = request.form['cantidad']
        precio = request.form['precio']
        unidad_medida = request.form['unidad_medida']
        update_producto(id, nombre, cantidad, precio, unidad_medida)
        flash('Producto actualizado exitosamente', 'success')
        return redirect(url_for('index'))
    return render_template('edit_product.html', producto=producto)


@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    delete_producto(id)
    flash('Producto eliminado exitosamente', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
