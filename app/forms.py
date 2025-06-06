from flask import flash
from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, StringField, FloatField, SelectField, IntegerField, SubmitField, ValidationError
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import Input
import logging as logger


class RangeInput(Input):
    input_type = 'range'
    validation_attrs = frozenset(['required', 'min', 'max', 'step'])


class ExerciseForm(FlaskForm):
    exercise_id = IntegerField('Exercise', validators=[])
    sets = IntegerField('Sets', validators=[Optional(), NumberRange(min=0)])
    reps = IntegerField('Reps', validators=[Optional(), NumberRange(min=0)])
    weight = FloatField('Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    order = IntegerField('Order', validators=[Optional()], default=0)
    is_edit = IntegerField('Is Edit', default=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from app.models import Exercise
        choices = [(0, 'Selecteer een oefening')] + [(e.id, e.name) for e in Exercise.query.all()]
        self.exercise_id.choices = choices
        if not self.exercise_id.data or self.exercise_id.data not in [c[0] for c in choices]:
            self.exercise_id.data = 0
        logger.debug(f"ExerciseForm initialized with exercise_id: {self.exercise_id.data}")


    class Meta:
        csrf = False  # Dit schakelt CSRF uit voor dit subformulier

class EditProfileForm(FlaskForm):
    name = StringField('Naam', validators=[DataRequired(), Length(min=1, max=64)])
    current_weight = FloatField('Huidige gewicht (kg)',
                                validators=[Optional(), NumberRange(min=20, max=300,
                                                                    message="Gewicht moet tussen 20 en 300 kg zijn")])
    weekly_workouts = IntegerField('Weekelijkse workouts',
                                   validators=[Optional(), NumberRange(min=0, max=20,
                                                                       message="Aantal workouts moet tussen 0 en 20 zijn")])
    fitness_goal = FloatField('Doel gewicht (kg)',
                              validators=[Optional(), NumberRange(min=20, max=300,
                                                                  message="Doel gewicht moet tussen 20 en 300 kg zijn")])
    submit = SubmitField('Profiel bijwerken')

    def __init__(self, original_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        from app.models import User
        if name.data != self.original_name:
            user = User.query.filter_by(name=name.data).first()
            if user is not None:
                raise ValidationError('Please use a different name.')

class AddWeightForm(FlaskForm):
    weight = FloatField('Gewicht (kg)',
                       validators=[DataRequired(), NumberRange(min=20, max=300,
                       message="Gewicht moet tussen 20 en 300 kg zijn")])
    notes = TextAreaField('Notities (optioneel)',
                         validators=[Optional(), Length(max=200)])
    submit = SubmitField('Gewicht toevoegen')

class NameForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Next')

class CurrentWeightForm(FlaskForm):
    current_weight = FloatField('Current Weight', widget=RangeInput())
    submit = SubmitField('Next')

class GoalWeightForm(FlaskForm):
    fitness_goal = FloatField('Streefgewicht (kg)', validators=[DataRequired(), NumberRange(min=30, max=500)])
    submit = SubmitField('Volgende')

class SearchExerciseForm(FlaskForm):
    search_term = StringField('Search Term')
    difficulty = SelectField('Difficulty', choices=[
        ('', 'Select Difficulty'),
        ('BEGINNER', 'Beginner'),
        ('INTERMEDIATE', 'Intermediate'),
        ('EXPERT', 'Expert')
    ])
    mechanic = SelectField('Mechanic', choices=[
        ('', 'Select Mechanic'),
        ('COMPOUND', 'Compound'),
        ('ISOLATION', 'Isolation'),
        ('NONE', 'Geen')
    ])
    category = SelectField('Category', choices=[
        ('', 'Select Category'),
        ('CARDIO', 'Cardio'),
        ('OLYMPIC_WEIGHTLIFTING', 'Olympic Weightlifting'),
        ('PLYOMETRICS', 'Plyometrics'),
        ('POWERLIFTING', 'Powerlifting'),
        ('STRENGTH', 'Strength'),
        ('STRETCHING', 'Stretching'),
        ('STRONGMAN', 'Strongman')
    ])
    equipment = SelectField('Equipment', choices=[
        ('', 'Select Equipment'),
        ('BANDS', 'Resistance Bands'),
        ('BARBELL', 'Barbell'),
        ('BODY_ONLY', 'Bodyweight'),
        ('CABLE', 'Cable'),
        ('DUMBBELL', 'Dumbbell'),
        ('EXERCISE_BALL', 'Exercise Ball'),
        ('E_Z_CURL_BAR', 'EZ Curl Bar'),
        ('FOAM_ROLL', 'Foam Roll'),
        ('KETTLEBELLS', 'Kettlebell'),
        ('MACHINE', 'Machine'),
        ('MEDICINE_BALL', 'Medicine Ball'),
        ('OTHER', 'Other')
    ])

    submit = SubmitField('Search')



class WorkoutPlanForm(FlaskForm):
    name = StringField('Plan Name', validators=[DataRequired(), Length(min=2, max=50)])
    exercises = FieldList(FormField(ExerciseForm), min_entries=0)
    submit = SubmitField('Create workout')

    def validate_exercises(self, field):
        exercise_ids = [exercise_form.exercise_id.data for exercise_form in field]
        logger.debug(f"Validating exercises: {exercise_ids}")
        for idx, (ex_id, exercise_form) in enumerate(zip(exercise_ids, field)):
            if ex_id == 0 and not exercise_form.is_edit.data:
                field.errors.append(f'Oefening {idx + 1}: Selecteer een geldige oefening.')
        duplicates = set([x for x in exercise_ids if exercise_ids.count(x) > 1 and x != 0])
        if duplicates:
            flash(f'Waarschuwing: Meerdere exemplaren van oefening(en): {", ".join(str(d) for d in duplicates)}',
                  'warning')


class DeleteWorkoutForm(FlaskForm):
    pass

class DeleteExerciseForm(FlaskForm):
    workout_plan_exercise_id = IntegerField('Workout Plan Exercise ID', validators=[DataRequired()])
    submit = SubmitField('Delete')


class ActiveWorkoutForm(FlaskForm):
    pass