# /main.py

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import datetime
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, LSTM

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
auth = HTTPBasicAuth()

SERP_API_KEY = 'your_serp_api_key'  # Replace with your actual SERP API key

users = {
    "admin": generate_password_hash("adminpassword"),
    "user": generate_password_hash("userpassword")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

db.create_all()

# Utility function to fetch search results from SERP API
def fetch_prices(query):
    url = f"https://serpapi.com/search.json?engine=google&q={query}&api_key={SERP_API_KEY}"
    response = requests.get(url)
    data = response.json()
    prices = []
    for result in data.get('shopping_results', []):
        prices.append({
            'title': result['title'],
            'price': result['price'],
            'link': result['link'],
            'image': result.get('thumbnail', '')  # Include image URL if available
        })
    return prices

# Price Comparison Endpoint
@app.route('/compare', methods=['GET'])
@auth.login_required
def compare_prices():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    prices = fetch_prices(query)
    return jsonify(prices)

# Price Tracking Endpoint
@app.route('/track', methods=['POST'])
@auth.login_required
def track_price():
    data = request.json
    product = data.get('product')
    price = data.get('price')
    if not product or not price:
        return jsonify({"error": "Product and price are required"}), 400
    new_price = PriceHistory(product=product, price=price)
    db.session.add(new_price)
    db.session.commit()
    return jsonify({"message": "Price tracked successfully"})

@app.route('/history/<product>', methods=['GET'])
@auth.login_required
def get_price_history(product):
    prices = PriceHistory.query.filter_by(product=product).all()
    if not prices:
        return jsonify({"error": "Product not found"}), 404
    price_list = [{"price": p.price, "timestamp": p.timestamp.isoformat()} for p in prices]
    return jsonify(price_list)

# Utility function to prepare data for LSTM model
def prepare_data(prices):
    prices = np.array([p.price for p in prices]).reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    prices = scaler.fit_transform(prices)
    X, y = [], []
    for i in range(3, len(prices)):
        X.append(prices[i-3:i, 0])
        y.append(prices[i, 0])
    X, y = np.array(X), np.array(y)
    X = np.reshape(X, (X.shape[0], X.shape[1], 1))
    return X, y, scaler

# Price Prediction Endpoint using LSTM
@app.route('/predict', methods=['POST'])
@auth.login_required
def predict_price():
    data = request.json
    product = data.get('product')
    prices = PriceHistory.query.filter_by(product=product).all()
    if not product or not prices:
        return jsonify({"error": "Product not found or no price history available"}), 400
    if len(prices) < 4:
        return jsonify({"error": "Not enough data to make a prediction"}), 400

    X, y, scaler = prepare_data(prices)

    model = Sequential()
    model.add(LSTM(units=50, return_sequences=True, input_shape=(X.shape[1], 1)))
    model.add(LSTM(units=50))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X, y, epochs=20, batch_size=1, verbose=0)

    last_prices = np.array([p.price for p in prices[-3:]]).reshape(-1, 1)
    last_prices = scaler.transform(last_prices)
    last_prices = np.reshape(last_prices, (1, last_prices.shape[0], 1))

    predicted_price = model.predict(last_prices)
    predicted_price = scaler.inverse_transform(predicted_price)[0][0]

    return jsonify({"predicted_price": predicted_price})

if __name__ == '__main__':
    app.run(debug=True)
