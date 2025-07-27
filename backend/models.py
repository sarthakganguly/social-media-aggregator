# File: backend/models.py

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class SocialChannel(db.Model):
    __tablename__ = 'social_channels'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    platform = db.Column(db.String(50), nullable=False) # e.g., 'linkedin'
    access_token = db.Column(db.Text, nullable=False)
    token_expires_at = db.Column(db.TIMESTAMP(timezone=True), nullable=True)
    created_at = db.Column(db.TIMESTAMP(timezone=True), server_default=db.func.now())
    channel_user_id = db.Column(db.String(255), nullable=True) # Can be nullable for now

    user = db.relationship('User', backref=db.backref('channels', lazy=True))

    def __repr__(self):
        return f'<SocialChannel {self.user.username} - {self.platform}>'
