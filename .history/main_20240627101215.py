from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import datetime
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense, LSTM

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

SERP_API_KEY = 'f89c9cc417e54bc265889dc64de7a0311943c49a466610515ebd2d898426ce1b'  # Replace with your actual SERP API key

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

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
        })
    return prices

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            return redirect(url_for('home', message="Login successful!"))
        else:
            return render_template('login.html', message="Invalid username or password")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return render_template('register.html', message="Username already exists")
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('home', message="User registered successfully"))
    return render_template('register.html')

@app.route('/compare_prices', methods=['GET'])
def compare_prices():
    query = request.args.get('query')
    if query:
        prices = fetch_prices(query)
        return render_template('compare.html', prices=prices)
    return render_template('compare.html')

@app.route('/track', methods=['GET', 'POST'])
def track_price():
    if request.method == 'POST':
        product = request.form['product']
        price = request.form['price']
        if product and price:
            new_price = PriceHistory(product=product, price=float(price))
            db.session.add(new_price)
            db.session.commit()
            return render_template('track.html', message="Price tracked successfully")
        else:
            return render_template('track.html', message="Product and price are required")
    return render_template('track.html')

@app.route('/history/<product>', methods=['GET'])
def get_price_history(product):
    prices = PriceHistory.query.filter_by(product=product).all()
    if not prices:
        return jsonify({"error": "Product not found"}), 404
    price_list = [{"price": p.price, "timestamp": p.timestamp.isoformat()} for p in prices]
    return jsonify(price_list)

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

@app.route('/predict', methods=['POST'])
def predict_price():
    product = request.json.get('product')
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
