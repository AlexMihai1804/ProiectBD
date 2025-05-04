from flask import Flask, jsonify, render_template
from db import Database
app = Flask(__name__)
database = Database()

@app.route('/api/products')
def api_products():
    products = database.get_stock()
    if not products:
        return jsonify({"error": "No products found"}), 404
    return jsonify(products)

@app.route('/')
def products_page():
    return render_template('products.html')

if __name__ == '__main__':
    app.run()
