from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    reviews = db.relationship('Review', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'

class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100))
    discount_value = db.Column(db.String(100))
    discount_min = db.Column(db.Float, nullable=True) 
    discount_max = db.Column(db.Float, nullable=True)  
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    reviews = db.relationship('Review', backref='location', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='location', lazy=True, cascade='all, delete-orphan')
    
    def get_average_rating(self):
        reviews = Review.query.filter_by(location_id=self.id).all()
        if not reviews:
            return 0
        total_rating = sum(review.rating for review in reviews)
        return round(total_rating / len(reviews), 1)
    
    def get_reviews_count(self):
        return Review.query.filter_by(location_id=self.id).count()
    
    def get_discount_display(self):
        if self.discount_min is not None and self.discount_max is not None:
            if self.discount_min == self.discount_max:
                return f"{int(self.discount_min)}%"
            else:
                return f"{int(self.discount_min)}-{int(self.discount_max)}%"
        elif self.discount_min is not None:
            return f"{int(self.discount_min)}%"
        elif self.discount_max is not None:
            return f"{int(self.discount_max)}%"
        elif self.discount_value:
            return self.discount_value
        else:
            return "По социальной карте"
    
    def __repr__(self):
        return f'<Location {self.name}>'

class Review(db.Model):
    __tablename__ = 'reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Review {self.id} by User {self.user_id}>'

class Favorite(db.Model):
    __tablename__ = 'favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'location_id', name='unique_user_location'),)
    
    def __repr__(self):
        return f'<Favorite User {self.user_id} Location {self.location_id}>'


class DiscountVote(db.Model):
    __tablename__ = 'discount_votes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False)
    is_valid = db.Column(db.Boolean, nullable=False, default=True)  # True = скидка действует
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'location_id', name='unique_user_location_vote'),)

    def __repr__(self):
        return f'<DiscountVote User {self.user_id} Location {self.location_id} Valid={self.is_valid}>'
