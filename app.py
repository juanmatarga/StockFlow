from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, g
import sqlite3
import pandas as pd
import matplotlib.dates as mdates
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
        subtotal REAL,
        descuento REAL,
        cargo_envio REAL,
        total REAL
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

def create_detalle_ventas_table():
    db = get_db()
    c = db.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS ventas_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id INTEGER,
        producto_id INTEGER,
        precio REAL,
        cantidad INTEGER,
        FOREIGN KEY (venta_id) REFERENCES ventas (id),
        FOREIGN KEY (producto_id) REFERENCES productos (id)
    )
    ''')
    db.commit()


with app.app_context():
    create_productos_table() 
    create_sales_table()
    create_detalle_ventas_table()
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


def add_venta(fecha, cliente, subtotal, descuento, cargo_envio, total):
    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO ventas (fecha, cliente, subtotal, descuento, cargo_envio, total)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (fecha, cliente, subtotal, descuento, cargo_envio, total))
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

def add_venta_detalle(venta_id, producto_id, cantidad):
    db = get_db()
    c = db.cursor()
    c.execute('''
    INSERT INTO ventas_detalle (venta_id, producto_id, cantidad)
    VALUES (?, ?, ?)
    ''', (venta_id, producto_id, cantidad))
    db.commit()

def get_venta_detalles(venta_id):
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM ventas_detalle WHERE venta_id = ?', (venta_id,))
    rows = c.fetchall()
    detalles = [dict(row) for row in rows]
    return detalles

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

@app.route('/api/analitica/<int:producto_id>', methods=['GET'])
def analitica(producto_id):
    # Conectar a la base de datos
    db = get_db()

    # Leer datos de ventas y compras desde la base de datos
    ventas_df = pd.read_sql_query(
        "SELECT fecha, cantidad FROM ventas WHERE producto_id = ? AND strftime('%Y-%m', fecha) = '2024-06'",
        db,
        params=[producto_id]
    )

    compras_df = pd.read_sql_query(
        "SELECT fecha, cantidad FROM compras WHERE strftime('%Y-%m', fecha) = '2024-06'",
        db
    )

    # Convertir las columnas de fecha a tipo datetime
    ventas_df['fecha'] = pd.to_datetime(ventas_df['fecha'])
    compras_df['fecha'] = pd.to_datetime(compras_df['fecha'])

    # Generar DataFrame con las fechas de junio de 2024
    fechas_junio = pd.date_range(start='2024-06-01', end='2024-06-30', freq='D')
    stock_df = pd.DataFrame({'fecha': fechas_junio})

    # Calcular el stock acumulado por día
    ventas_agrupadas = ventas_df.groupby('fecha').sum().reset_index()
    compras_agrupadas = compras_df.groupby('fecha').sum().reset_index()

    stock_df = stock_df.merge(ventas_agrupadas, on='fecha', how='left').fillna(0)
    stock_df = stock_df.merge(compras_agrupadas, on='fecha', how='left', suffixes=('_venta', '_compra')).fillna(0)
    stock_df['stock'] = stock_df['cantidad_compra'] - stock_df['cantidad_venta']
    stock_df['stock_acumulado'] = stock_df['stock'].cumsum()

    # Graficar el stock por día
    plt.figure(figsize=(10, 5))
    plt.plot(stock_df['fecha'], stock_df['stock_acumulado'], marker='o', linestyle='-')
    plt.title(f'Stock acumulado por día en junio de 2024 (Producto ID: {producto_id})')
    plt.xlabel('Fecha')
    plt.ylabel('Stock acumulado')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('var_stock.png')
    plt.close()

    # Graficar las compras por día
    plt.figure(figsize=(10, 5))
    plt.bar(compras_df['fecha'], compras_df['cantidad'], color='blue')
    plt.title('Compras por día en junio de 2024')
    plt.xlabel('Fecha')
    plt.ylabel('Cantidad')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('compras.png')
    plt.close()

    # Graficar las ventas por día
    plt.figure(figsize=(10, 5))
    plt.bar(ventas_df['fecha'], ventas_df['cantidad'], color='red')
    plt.title(f'Ventas por día en junio de 2024 (Producto ID: {producto_id})')
    plt.xlabel('Fecha')
    plt.ylabel('Cantidad')
    plt.grid(True)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('ventas.png')
    plt.close()

    return jsonify({"message": "Gráficos generados correctamente"})

# Rutas para la página web
@app.route('/carga_venta', methods=['POST', 'GET'])
def carga_venta():
    db = get_db()
    c = db.cursor()
    c.execute('SELECT * FROM productos')
    productos = c.fetchall()
    c.execute('SELECT * FROM ventas')
    ventas = c.fetchall()

    if request.method == 'POST':
        data = request.get_json()
        print("Datos recibidos:", data)  # Log de datos recibidos
        items = data['items']
        fecha = data['fecha']
        cliente = data['cliente']

        if not items:
            flash('No se encontraron productos en el carrito.', 'error')
            return jsonify(success=False, error='No se encontraron productos en el carrito.')

        try:
            # Calcular totales
            subtotal = sum(item['cantidad'] * item['precio'] for item in items)
            descuento = sum(item['descuento'] for item in items)
            cargo_envio = sum(item['envio'] for item in items)
            total = subtotal - descuento + cargo_envio

            print(f"Subtotal: {subtotal}, Descuento: {descuento}, Cargo Envío: {cargo_envio}, Total: {total}")

            # Insertar la venta en la tabla 'ventas'
            c.execute('''
                INSERT INTO ventas (fecha, cliente, subtotal, descuento, cargo_envio, total)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (fecha, cliente, subtotal, descuento, cargo_envio, total))
            venta_id = c.lastrowid
            print("Venta ID:", venta_id)  # Log de venta_id

            # Insertar cada producto en la tabla 'ventas_detalle'
            for item in items:
                print("Insertando item:", item)  # Log de cada item
                c.execute('''
                    INSERT INTO ventas_detalle (venta_id, producto_id, cantidad, precio)
                    VALUES (?, ?, ?, ?)
                ''', (venta_id, item['id'], item['cantidad'], item['precio']))

                # Actualizar el stock del producto
                c.execute('''
                    UPDATE productos
                    SET cantidad = cantidad - ?
                    WHERE id = ?
                ''', (item['cantidad'], item['id']))

            db.commit()

            flash('Venta realizada con éxito.', 'success')
            return jsonify(success=True)

        except Exception as e:
            db.rollback()
            print("Error al registrar la venta:", str(e))  # Log del error
            flash(f'Error al registrar la venta: {str(e)}', 'error')
            return jsonify(success=False, error=str(e))

        finally:
            db.close()
    else:
        db.close()
        return render_template('carga_venta.html', productos=productos, ventas=ventas)


@app.route('/carga_compras', methods=['GET', 'POST'])
def carga_compras():
    db = get_db()
    c = db.cursor()

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
