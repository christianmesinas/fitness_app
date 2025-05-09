from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, ValidationError, NumberRange
from app.models import User
from app import db

class QuestionnaireForm(FlaskForm):
    name = StringField(
        'Wat is je naam?',
        validators=[DataRequired(), Length(min=2, max=64)]
    )
    huidige_gewicht = SelectField(
        'Wat is je huidige gewicht?',
        validators=[DataRequired(), NumberRange(min=25, max=300,)]
    )
    doel_gewicht = SelectField(
        'Wat is je doel gewicht?',
        validators=[DataRequired(), NumberRange(min=25, max=300, )]
    )
    workout_freq = SelectField(
        'Hoeveel workouts wil je doen per week?',
        validators=[DataRequired(), NumberRange(min=1, max=14, )]
    )
    submit = SubmitField('Versturen')



#class PostForm(FlaskForm):
#    post = TextAreaField('Say something', validators=[DataRequired(), Length(min=1, max=140)])
#    submit = SubmitField('Submit')

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=140)])
    submit = SubmitField('Submit')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(db.select(User).where(User.username == username.data))
            if user is not None:
                raise ValidationError('Please use a different username.')

class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

class MessageForm(FlaskForm):
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=140)])
    submit = SubmitField('Submit')