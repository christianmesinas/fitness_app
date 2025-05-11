# /app/app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, SubmitField, SelectField
from wtforms.fields import FieldList, FormField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from app.models import User, Exercise
from app import db

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    current_weight = FloatField('Current Weight (kg)', validators=[NumberRange(min=0.1, max=300)])
    weekly_workouts = IntegerField('Weekly Workouts', validators=[NumberRange(min=0, max=7)])
    submit = SubmitField('Save Changes')
    name = StringField('Naam', validators=[DataRequired(), Length(min=2, max=100)])

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(db.select(User).where(User.username == username.data))
            if user is not None:
                raise ValidationError('Please use a different username.')

class SearchExerciseForm(FlaskForm):
    search_term = StringField('Search Exercises', validators=[DataRequired()])
    submit = SubmitField('Search')

class WorkoutPlanExerciseForm(FlaskForm):
    exercise_id = SelectField('Exercise', coerce=int, validators=[DataRequired()])
    sets = IntegerField('Sets', validators=[DataRequired(), NumberRange(min=1)])
    reps = IntegerField('Reps', validators=[DataRequired(), NumberRange(min=1)])
    weight = FloatField('Weight (kg)', validators=[NumberRange(min=0)])

    def __init__(self, *args, **kwargs):
        super(WorkoutPlanExerciseForm, self).__init__(*args, **kwargs)
        self.exercise_id.choices = [(e.id, e.name) for e in db.session.scalars(db.select(Exercise).order_by(Exercise.name)).all()]

class WorkoutPlanForm(FlaskForm):
    name = StringField('Plan Name', validators=[DataRequired(), Length(max=100)])
    exercises = FieldList(FormField(WorkoutPlanExerciseForm), min_entries=1)
    submit = SubmitField('Create Plan')


class CurrentWeightForm(FlaskForm):
    current_weight = FloatField('Current Weight (kg)', validators=[DataRequired(), NumberRange(min=0.1, max=300)])
    submit = SubmitField('Next')

class GoalWeightForm(FlaskForm):
    fitness_goal = FloatField('Goal Weight (kg)', validators=[DataRequired(), NumberRange(min=0.1, max=300)])
    submit = SubmitField('Next')

class ExerciseLogForm(FlaskForm):
    exercise_id = SelectField('Exercise', coerce=int, validators=[DataRequired()])
    sets = IntegerField('Sets', validators=[DataRequired(), NumberRange(min=1)])
    reps = IntegerField('Reps', validators=[DataRequired(), NumberRange(min=1)])
    weight = FloatField('Weight (kg)', validators=[NumberRange(min=0)])
    submit = SubmitField('Log Exercise')

    def __init__(self, *args, **kwargs):
        super(ExerciseLogForm, self).__init__(*args, **kwargs)
        self.exercise_id.choices = [(e.id, e.name) for e in db.session.scalars(db.select(Exercise).order_by(Exercise.name)).all()]

class NameForm(FlaskForm):
    name = StringField('Naam', validators=[DataRequired(), Length(min=2, max=100)])
    submit = SubmitField('Volgende')