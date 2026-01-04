from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify 
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/student_discounts'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
app.config['YANDEX_MAPS_API_KEY'] = os.environ.get('YANDEX_MAPS_API_KEY', '')

from models import db, User, Location, Review, Favorite, DiscountVote
db.init_app(app) 

@app.route('/')
def index():
    category = request.args.get('category', '')
    search_query = request.args.get('search', '')
    
    locations = Location.query
    
    if search_query:
        locations = locations.filter(Location.name.contains(search_query) | Location.address.contains(search_query))
    
    if category:
        locations = locations.filter_by(category=category)
    
    locations = locations.all()
    
    categories = db.session.query(Location.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]

    return render_template('index.html', locations=locations, categories=categories, current_category=category, search_query=search_query)

@app.route('/map')
def map_view():
    locations = Location.query.filter (Location.latitude.isnot(None), Location.longitude.isnot(None)).all()

    map_points = []
    for loc in locations:
        map_points.append({
            'id': loc.id,
            'name': loc.name,
            'address': loc.address,
            'discount': loc.get_discount_display() or '',
            'category': loc.category or '',
            'lat': float(loc.latitude),
            'lon': float(loc.longitude),
        })

    return render_template(
        'map.html',
        map_points=map_points,
        total_points=len(map_points),
        yandex_maps_api_key=app.config.get('YANDEX_MAPS_API_KEY', '')
    )

@app.route('/location/<int:location_id>')
def location_detail(location_id):
    location = Location.query.get_or_404(location_id)
    reviews = Review.query.filter_by(location_id=location_id).order_by(Review.created_at.desc()).all()
    
    avg_rating = location.get_average_rating()

    similar_locations = Location.query.filter(Location.category == location.category, Location.id != location_id).limit(3).all() 

    
    is_favorite = False 
    user_vote = None
    if 'user_id' in session:
        favorite = Favorite.query.filter_by(user_id=session['user_id'], location_id=location_id). first() 
        is_favorite = favorite is not None
        user_vote = DiscountVote.query.filter_by(user_id=session['user_id'], location_id=location_id). first()

    valid_votes = DiscountVote.query.filter_by(location_id=location_id, is_valid=True).count()
    invalid_votes = DiscountVote.query.filter_by(location_id=location_id, is_valid=False).count()
    
    return render_template('location_detail.html',
                         location=location,
                         reviews=reviews,
                         avg_rating=avg_rating,
                         similar_locations=similar_locations,
                         is_favorite=is_favorite,
                         valid_votes=valid_votes,
                         invalid_votes=invalid_votes,
                         user_vote=user_vote)


@app.route('/vote_discount/<int:location_id>', methods=['POST'])
def vote_discount(location_id):
    if 'user_id' not in session:
        flash('Необходимо войти в систему', 'warning')
        return redirect(url_for('login'))

    location = Location.query.get_or_404(location_id)
    is_valid_str = request.form.get('is_valid', '1')
    is_valid = is_valid_str == '1'

    vote = DiscountVote.query.filter_by(user_id=session['user_id'], location_id=location_id).first()

    if vote:
        vote.is_valid = is_valid
    else:
        vote = DiscountVote(user_id=session['user_id'], location_id=location_id,is_valid=is_valid)
        db.session.add(vote)

    db.session.commit()
    flash('Спасибо за ваш ответ!', 'success')
    return redirect(url_for('location_detail', location_id=location.id))

@app.route('/add_review/<int:location_id>', methods=['POST'])
def add_review(location_id):
    if 'user_id' not in session:
        flash('Необходимо войти в систему', 'warning')
        return redirect(url_for('login'))
    
    text = request.form.get('text', '').strip()
    rating = int(request.form.get('rating', 5))
    
    if not text:
        flash('Отзыв не может быть пустым', 'danger')
        return redirect(url_for('location_detail', location_id=location_id))
    
    if rating < 1 or rating > 5:
        rating = 5
    
    review = Review(user_id=session['user_id'], location_id=location_id, text=text,rating=rating)
    
    db.session.add(review)
    db.session.commit()
    
    flash('Отзыв успешно добавлен!', 'success')
    return redirect(url_for('location_detail', location_id=location_id))

@app.route('/toggle_favorite/<int:location_id>', methods=['POST'])
def toggle_favorite(location_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Необходимо войти в систему'}), 401
    
    favorite = Favorite.query.filter_by(user_id=session['user_id'], location_id=location_id).first()
    
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
        return jsonify({'status': 'removed', 'message': 'Удалено из избранного'})
    else:
        favorite = Favorite(
            user_id=session['user_id'],
            location_id=location_id
        )
        db.session.add(favorite)
        db.session.commit()
        return jsonify({'status': 'added', 'message': 'Добавлено в избранное'})

@app.route('/favorites')
def favorites():
    if 'user_id' not in session:
        flash('Необходимо войти в систему', 'warning')
        return redirect(url_for('login'))
    
    favorites = Favorite.query.filter_by(user_id=session['user_id']).all()
    location_ids = [f.location_id for f in favorites]
    locations = Location.query.filter(Location.id.in_(location_ids)).all()
    
    return render_template('favorites.html', locations=locations)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not username or not email or not password:
            flash('Все поля обязательны для заполнения', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return render_template('register.html')
        
        user = User(username=username, email=email, password=generate_password_hash(password))
        
        db.session.add(user)
        db.session.commit()
        
        flash('Регистрация успешна! Войдите в систему', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Необходимо войти в систему', 'warning')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    reviews_count = Review.query.filter_by(user_id=user.id).count()
    favorites_count = Favorite.query.filter_by(user_id=user.id).count()
    
    return render_template('profile.html', user=user, reviews_count=reviews_count, favorites_count=favorites_count)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001)
