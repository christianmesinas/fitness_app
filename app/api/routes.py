# app/api/routes.py
from flask import jsonify, request
from app import db
from app.models import User
from app.api import bp
import sqlalchemy as sa

@bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email is required'}), 400
    user = db.session.scalar(sa.select(User).where(User.email == data['email']))
    if not user:
        user = User(
            email=data['email'],
            username=data.get('username', data['email'].split('@')[0]),
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.debug(f"User created: {user.email}")
    return jsonify({'message': 'User created'}), 201