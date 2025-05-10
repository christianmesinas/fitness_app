from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, IntegerField, TextAreaField, SubmitField, SelectField, BooleanField, DateField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError
from app.models import User, Exercise, WorkoutPlan, Muscle, ExperienceLevel, Equipment
from app import db

class QuestionnaireForm(FlaskForm):
    username = StringField('Wat is je naam?', validators=[DataRequired(), Length(min=2, max=64)])
    current_weight = FloatField('Wat is je huidige gewicht (kg)?', validators=[DataRequired(), NumberRange(min=25, max=300)])
    fitness_goal = StringField('Wat is je fitnessdoel? (bijv. spieropbouw, vetverlies)', validators=[Optional(), Length(max=64)])
    experience_level = SelectField('Wat is je ervaringsniveau?', choices=[(l.value, l.value.capitalize()) for l in ExperienceLevel], validators=[Optional()])
    weekly_workouts = IntegerField('Hoeveel workouts wil je doen per week?', validators=[DataRequired(), NumberRange(min=1, max=14)])
    submit = SubmitField('Versturen')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError('Deze gebruikersnaam is al in gebruik. Kies een andere.')

class EditProfileForm(FlaskForm):
    username = StringField('Gebruikersnaam', validators=[DataRequired(), Length(min=2, max=64)])
    fitness_goal = StringField('Fitnessdoel', validators=[Optional(), Length(max=64)])
    experience_level = SelectField('Ervaringsniveau', choices=[(l.value, l.value.capitalize()) for l in ExperienceLevel], validators=[Optional()])
    current_weight = FloatField('Huidig gewicht (kg)', validators=[Optional(), NumberRange(min=25, max=300)])
    weekly_workouts = IntegerField('Wekelijkse workouts', validators=[Optional(), NumberRange(min=1, max=14)])
    submit = SubmitField('Opslaan')

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(sa.select(User).where(User.username == username.data))
            if user is not None:
                raise ValidationError('Deze gebruikersnaam is al in gebruik. Kies een andere.')

class SearchExerciseForm(FlaskForm):
    query = StringField('Zoek oefeningen', validators=[Optional()])
    muscle = SelectField('Spiergroep', choices=[('', 'Alle')] + [(m.value, m.value.capitalize()) for m in Muscle], validators=[Optional()])
    level = SelectField('Niveau', choices=[('', 'Alle')] + [(l.value, l.value.capitalize()) for l in ExperienceLevel], validators=[Optional()])
    equipment = SelectField('Apparatuur', choices=[('', 'Alle')] + [(e.value, e.value.capitalize()) for e in Equipment], validators=[Optional()])
    submit = SubmitField('Zoeken')

class WorkoutPlanForm(FlaskForm):
    name = StringField('Naam van het plan', validators=[DataRequired(), Length(min=1, max=100)])
    start_date = DateField('Startdatum', validators=[Optional()])
    end_date = DateField('Einddatum', validators=[Optional()])
    submit = SubmitField('Plan aanmaken')

class ExerciseLogForm(FlaskForm):
    exercise_id = SelectField('Oefening', coerce=str, validators=[DataRequired()])
    workout_plan_id = SelectField('Workoutplan', coerce=int, validators=[Optional()])
    completed = BooleanField('Voltooid')
    sets = IntegerField('Sets', validators=[Optional(), NumberRange(min=1)])
    reps = IntegerField('Herhalingen', validators=[Optional(), NumberRange(min=1)])
    weight = FloatField('Gewicht (kg)', validators=[Optional(), NumberRange(min=0)])
    duration = IntegerField('Duur (minuten)', validators=[Optional(), NumberRange(min=0)])
    notes = TextAreaField('Notities', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Oefening loggen')

    def __init__(self, user_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate exercise choices
        self.exercise_id.choices = [(e.id, e.name) for e in Exercise.query.order_by(Exercise.name).all()]
        # Populate workout plan choices for the user
        if user_id:
            self.workout_plan_id.choices = [('', 'Geen')] + [(p.id, p.name) for p in WorkoutPlan.query.filter_by(user_id=user_id).order_by(WorkoutPlan.name).all()]
        else:
            self.workout_plan_id.choices = [('', 'Geen')]