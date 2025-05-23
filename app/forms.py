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
    name = StringField('Name', validators=[DataRequired(), Length(min=4, max=20)])
    current_weight = FloatField('Current Weight (kg)', validators=[NumberRange(min=20, max=300)])
    weekly_workouts = IntegerField('Weekly Workouts', validators=[NumberRange(min=0, max=7)])
    submit = SubmitField('Save')

    def __init__(self, original_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        from app.models import User
        if name.data != self.original_name:
            user = User.query.filter_by(name=name.data).first()
            if user is not None:
                raise ValidationError('Please use a different name.')

class NameForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Next')

class CurrentWeightForm(FlaskForm):
    current_weight = FloatField('Current Weight (kg)', validators=[DataRequired(), NumberRange(min=20, max=300)])
    submit = SubmitField('Next')

class GoalWeightForm(FlaskForm):
    fitness_goal = FloatField('Streefgewicht (kg)', validators=[DataRequired(), NumberRange(min=30, max=500)])
    submit = SubmitField('Volgende')

class SearchExerciseForm(FlaskForm):
    search_term = StringField('Search Term')
    difficulty = SelectField('Difficulty', choices=[('', 'Select Difficulty'), ('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')])
    muscle_group = SelectField('Muscle Group', choices=[('', 'Select Muscle'), ('chest', 'Chest'), ('back', 'Back'), ('shoulders', 'Shoulders'), ('arms', 'Arms'), ('core', 'Core'), ('legs', 'Legs'), ('glutes', 'Glutes')])
    exercise_type = SelectField('Equipment', choices=[('', 'Select Equipment'), ('dumbbell', 'Dumbbell'), ('barbell', 'Barbell'), ('bodyweight', 'Bodyweight'), ('kettlebell', 'Kettlebell'), ('resistance_band', 'Resistance Band'), ('machine', 'Machine'), ('cable', 'Cable')])
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