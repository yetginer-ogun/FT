from flask import Flask, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from transformers import pipeline
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Veritabanı ayarları
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Kullanıcı modeli
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Duygu analizi modelleri
models = {
    "turkish": pipeline("sentiment-analysis", model="savasy/bert-base-turkish-sentiment-cased"),
    "english": pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
}

# Varsayılan dil
default_language = 'turkish'

# Yükleme klasörü
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("home.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Kullanıcıyı bul
        user = User.query.filter_by(username=username).first()
        if password != user.password:
            return render_template('login.html', error="Geçersiz kullanıcı adı veya şifre!")

        # Oturum aç
        session['user_id'] = user.id
        session['username'] = user.username
        return render_template('home.html')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Şifrelerin eşleştiğini kontrol et
        if password != confirm_password:
            return render_template('register.html', error="Şifreler uyuşmuyor!")

        # Kullanıcı adının zaten var olup olmadığını kontrol et
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('register.html', error="Bu kullanıcı adı zaten alınmış!")

        # Yeni kullanıcıyı kaydet
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_input = request.form['text']
    language = session.get('language', default_language)

    sentiment_analyzer = models[language]
    result = sentiment_analyzer(user_input)[0]

    # Çıktıyı yazdırarak inceleyelim
    print("Model Output:", result)

    # Etiket eşlemesi
    sentiment_translation = {
        "turkish": {"POSITIVE": "Pozitif", "NEGATIVE": "Negatif"},
        "english": {"POSITIVE": "Positive", "NEGATIVE": "Negative"}
    }

    # Modelin döndürdüğü etiketi kontrol et
    sentiment = result['label']
    score = round(result['score'], 2)
    print (sentiment)
    return render_template('result.html', text=user_input, sentiment=sentiment  , score=score, language=language)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    if 'file' not in request.files:
        return redirect(url_for('home'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('home'))

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    language = session.get('language', default_language)
    sentiment_analyzer = models[language]

    results = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            result = sentiment_analyzer(line)[0]
            sentiment_translation = {
                "turkish": {"POSITIVE": "Pozitif", "NEGATIVE": "Negatif"},
                "english": {"POSITIVE": "Positive", "NEGATIVE": "Negative"}
            }
            sentiment = sentiment_translation[language].get(result['label'], "Unknown")
            score = round(result['score'], 2)
            results.append({"text": line, "sentiment": sentiment, "score": score})

    # Kullanıcı geçmişine ekle
    sentiment = sentiment_translation[language].get(result['label'], "Unknown")
    score = round(result['score'], 2)

    return render_template('result.html', results=results, language=language)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/change_language', methods=['POST'])
def change_language():
    if 'username' not in session:
        return redirect(url_for('login'))

    selected_language = request.form.get('language')
    session['language'] = selected_language
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
