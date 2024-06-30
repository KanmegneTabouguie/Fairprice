from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import requests
import datetime
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense, LSTM

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///prices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

SERP_API_KEY = 'your api key from serp api'

class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product = db.Column(db.String(100), nullable=False)
    predicted_price = db.Column(db.Float, nullable=False)
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
            'image': result.get('thumbnail', '')
        })
    return prices

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/compare_prices', methods=['GET'])
def compare_prices():
    query = request.args.get('query')
    prices = []
    if query:
        prices = fetch_prices(query)
    return render_template('compare.html', prices=prices, query=query)

@app.route('/track', methods=['GET', 'POST'])
def track_price():
    if request.method == 'POST':
        product = request.form['product']
        price = request.form['price']
        if product and price:
            new_price = PriceHistory(product=product, price=float(price))
            db.session.add(new_price)
            db.session.commit()
            flash("Price tracked successfully", "success")
        else:
            flash("Product and price are required", "danger")
    tracked_products = db.session.query(PriceHistory.product).distinct().all()
    return render_template('track.html', tracked_products=[p[0] for p in tracked_products])

@app.route('/history/<product>', methods=['GET'])
def get_price_history(product):
    prices = PriceHistory.query.filter_by(product=product).all()
    predictions = Prediction.query.filter_by(product=product).all()
    if not prices:
        flash("Product not found", "danger")
        return redirect(url_for('track_price'))
    return render_template('history.html', product=product, prices=prices, predictions=predictions)

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

@app.route('/predict', methods=['GET', 'POST'])
def predict_price():
    if request.method == 'POST':
        product = request.form['product']
        prices = PriceHistory.query.filter_by(product=product).all()
        if not product or not prices:
            flash("Product not found or no price history available", "danger")
            return redirect(url_for('predict_price'))
        if len(prices) < 4:
            flash("Not enough data to make a prediction", "danger")
            return redirect(url_for('predict_price'))

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

        new_prediction = Prediction(product=product, predicted_price=predicted_price)
        db.session.add(new_prediction)
        db.session.commit()

        return render_template('predict.html', product=product, predicted_price=predicted_price)
    return render_template('predict_form.html')

@app.route('/predictions', methods=['GET'])
def view_predictions():
    products = db.session.query(Prediction.product).distinct().all()
    return render_template('predictions.html', products=[p[0] for p in products])

@app.route('/predictions/<product>', methods=['GET'])
def view_product_predictions(product):
    predictions = Prediction.query.filter_by(product=product).all()
    if not predictions:
        flash("No predictions found for this product", "danger")
        return redirect(url_for('view_predictions'))
    return render_template('product_predictions.html', product=product, predictions=predictions)

if __name__ == '__main__':
    app.run(debug=True)
