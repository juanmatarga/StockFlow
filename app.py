from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, g
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

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


# PRODUCTOS
def create_productos_table():
    db = get_db()
    c = db.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        cantidad INTEGER,
        precio REAL,
        unidad_medida TEXT DEFAULT 'unidades'
    )
    ''')
    db.commit()


# VENTAS
def create_sales_table():
    db = get_db()
    c = db.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        cliente TEXT,
        producto_id INTEGER,
        producto_nombre TEXT,
        cantidad INTEGER,
        precio_venta REAL,
        subtotal REAL,
        descuento REAL,
        cargo_envio REAL,
        total REAL,
        FOREIGN KEY (producto_id) REFERENCES productos (id)
    )
    ''')
    db.commit()

# COMPRAS
def create_compras_table():
    db = get_db()
    c = db.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS compras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        producto_id INTEGER,
        producto_nombre TEXT,
        cantidad INTEGER,
        precio REAL,
        total REAL,
        FOREIGN KEY (producto_id) REFERENCES productos (id)
    )
    ''')
    db.commit()


with app.app_context():
    create_productos_table() 
    create_sales_table()
    create_compras_table()

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


def add_venta(cliente, producto_id, producto_nombre, cantidad, precio_venta, subtotal, descuento, cargo_envio, total):
    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO ventas (cliente, producto_id, producto_nombre, cantidad, precio_venta, subtotal, descuento, cargo_envio, total)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (cliente, producto_id, producto_nombre, cantidad, precio_venta, subtotal, descuento, cargo_envio, total))
    db.commit()


def get_ventas():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM ventas")
    rows = c.fetchall()
    ventas = [dict(row) for row in rows]
    return ventas


def get_compras():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM compras")
    rows = c.fetchall()
    compras = [dict(row) for row in rows]
    return compras


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
    return jsonify({'message': 'Producto eliminado'}), 200

@app.route('/api/compras', methods=['POST'])
def add_compra():
    data = request.json
    producto_id = data['producto_id']
    cantidad = data['cantidad']
    precio = data['precio']

    producto = get_producto(producto_id)
    if producto:
        nuevo_precio = ((producto['cantidad'] * producto['precio']) + (cantidad * precio)) / (producto['cantidad'] + cantidad)
        nuevo_stock = producto['cantidad'] + cantidad

        update_producto(producto_id, producto['nombre'], nuevo_stock, nuevo_precio, producto['unidad_medida'])

        return jsonify({'message': 'Compra cargada exitosamente'}), 201
    return jsonify({'error': 'Producto no encontrado'}), 404

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

# Rutas para la página web
@app.route('/carga_venta', methods=['GET', 'POST'])
def carga_venta():
    if request.method == 'POST':
        cliente = request.form['cliente']
        producto_id = request.form['producto']
        cantidad = float(request.form['cantidad'])
        precio_venta = float(request.form['precio_venta'])
        descuento = float(request.form['descuento'])
        cargo_envio = float(request.form['cargo_envio'])
        fecha = request.form['fecha']

        subtotal = precio_venta * cantidad
        total = subtotal - descuento + cargo_envio

        db = get_db()
        c = db.cursor()

        # Parche a acomodar, insertar producto_nombre en la tabla ventas y descontar stock
        c.execute('SELECT * FROM productos WHERE id = ?', (producto_id,))
        producto = c.fetchone()
        producto_nombre = producto['nombre']
        if producto:
            nuevo_stock = producto['cantidad'] - cantidad
            c.execute('UPDATE productos SET cantidad = ? WHERE id = ?', (nuevo_stock, producto_id))
        
        # Insertar la nueva venta
        c.execute('''
            INSERT INTO ventas (cliente, producto_id, producto_nombre, cantidad, precio_venta, descuento, cargo_envio, total, fecha, subtotal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cliente, producto_id, producto_nombre, cantidad, precio_venta, descuento, cargo_envio, total, fecha, subtotal))

        db.commit()
        return redirect(url_for('carga_venta'))

    db = get_db()
    c = db.cursor()
    c.execute('SELECT id, nombre, cantidad, precio FROM productos')
    productos = c.fetchall() 

    c.execute('''
        SELECT v.*, p.nombre as producto_nombre 
        FROM ventas v 
        JOIN productos p ON v.producto_id = p.id
    ''')
    ventas = c.fetchall()

    return render_template('carga_venta.html', productos=productos, ventas=ventas)


@app.route('/carga_compras', methods=['GET', 'POST'])
def carga_compras():
    if request.method == 'POST':
        producto_id = request.form['producto']
        cantidad = float(request.form['cantidad'])
        precio = float(request.form['precio'])
        fecha = request.form['fecha']

        db = get_db()
        c = db.cursor()

        c.execute('SELECT * FROM productos WHERE id = ?', (producto_id,))
        producto = c.fetchone()

        if producto:
            nuevo_precio = ((producto['cantidad'] * producto['precio']) + (cantidad * precio)) / (producto['cantidad'] + cantidad)
            nuevo_stock = producto['cantidad'] + cantidad

            c.execute('''
                UPDATE productos
                SET cantidad = ?, precio = ?
                WHERE id = ?
            ''', (nuevo_stock, nuevo_precio, producto_id))

            c.execute('''
                INSERT INTO compras (producto_id, producto_nombre, cantidad, precio, total, fecha)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (producto_id, producto['nombre'], cantidad, precio, cantidad * precio, fecha))

            db.commit()
            return redirect(url_for('carga_compras'))

    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM productos')
    productos = c.fetchall()

    c.execute('''
        SELECT c.*, p.nombre as producto_nombre 
        FROM compras c 
        JOIN productos p ON c.producto_id = p.id
    ''')
    compras = c.fetchall()

    return render_template('carga_compras.html', productos=productos, compras=compras)

@app.route('/')
def index():
    productos = get_productos()
    return render_template('index.html', productos=productos)


@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        nombre = request.form['nombre']
        unidad_medida = request.form['unidad_medida']
        add_producto(nombre, 0, 0, unidad_medida)
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
