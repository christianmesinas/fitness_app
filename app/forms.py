from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, IntegerField, SubmitField, ValidationError
from wtforms import FieldList, FormField
from wtforms.validators import DataRequired, Length, NumberRange

class ExerciseForm(FlaskForm):
    exercise_id = SelectField('Exercise', coerce=int, validators=[DataRequired()])
    sets = IntegerField('Sets', validators=[DataRequired(), NumberRange(min=1)])
    reps = IntegerField('Reps', validators=[DataRequired(), NumberRange(min=1)])
    weight = FloatField('Weight (kg)', validators=[NumberRange(min=0)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Exercise
        self.exercise_id.choices = [(e.id, e.name) for e in Exercise.query.all()]

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    current_weight = FloatField('Current Weight (kg)', validators=[NumberRange(min=20, max=300)])
    weekly_workouts = IntegerField('Weekly Workouts', validators=[NumberRange(min=0, max=7)])
    submit = SubmitField('Save')

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        from app.models import User
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')

class NameForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Next')

class CurrentWeightForm(FlaskForm):
    current_weight = FloatField('Current Weight (kg)', validators=[DataRequired(), NumberRange(min=20, max=300)])
    submit = SubmitField('Next')

class GoalWeightForm(FlaskForm):
    fitness_goal = SelectField('Fitness Goal', choices=[
        ('lose_weight', 'Lose Weight'),
        ('gain_muscle', 'Gain Muscle'),
        ('maintain', 'Maintain')
    ], validators=[DataRequired()])
    submit = SubmitField('Next')

class SearchExerciseForm(FlaskForm):
    search_term = StringField('Search Exercise', validators=[DataRequired()])
    submit = SubmitField('Search')

class WorkoutPlanForm(FlaskForm):
    name = StringField('Plan Name', validators=[DataRequired(), Length(min=2, max=50)])
    exercises = FieldList(FormField(ExerciseForm), min_entries=1)
    submit = SubmitField('Create Plan')

class ExerciseLogForm(FlaskForm):
    exercise_id = SelectField('Exercise', coerce=int, validators=[DataRequired()])
    sets = IntegerField('Sets', validators=[DataRequired(), NumberRange(min=1)])
    reps = IntegerField('Reps', validators=[DataRequired(), NumberRange(min=1)])
    weight = FloatField('Weight (kg)', validators=[NumberRange(min=0)])
    submit = SubmitField('Log Exercise')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Exercise
        self.exercise_id.choices = [(e.id, e.name) for e in Exercise.query.all()]