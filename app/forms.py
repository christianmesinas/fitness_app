from flask import flash
from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, StringField, FloatField, SelectField, IntegerField, SubmitField, ValidationError
from wtforms.fields.simple import TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import Input
import logging as logger


class RangeInput(Input):
    """
    Aangepaste WTForms-widget voor HTML range-inputs.
    Notities:
        - Gebruikt in CurrentWeightForm voor een interactieve gewichtsinvoer.
        - Ondersteunt validatie-attributen zoals min, max, en step.
    """
    input_type = 'range'
    validation_attrs = frozenset(['required', 'min', 'max', 'step'])


class ExerciseForm(FlaskForm):
    """
    Subformulier voor het toevoegen of bewerken van een oefening in een workout-plan.
    Notities:
        - CSRF is uitgeschakeld omdat dit een subformulier is binnen WorkoutPlanForm.
        - Dynamische keuzes voor exercise_id worden geladen uit de Exercise-tabel.
        - Logging wordt gebruikt voor debugging van initialisatie.
    """
    exercise_id = IntegerField('Exercise', validators=[])
    sets = IntegerField('Sets', validators=[Optional(), NumberRange(min=0)])
    reps = IntegerField('Reps', validators=[Optional(), NumberRange(min=0)])
    weight = FloatField('Weight (kg)', validators=[Optional(), NumberRange(min=0)])
    order = IntegerField('Order', validators=[Optional()], default=0)
    is_edit = IntegerField('Is Edit', default=0)

    def __init__(self, *args, **kwargs):
        """
        Initialiseer het formulier met dynamische oefeningkeuzes.

        Notities:
            - Laadt alle oefeningen uit de database voor de exercise_id dropdown.
            - Stelt exercise_id in op 0 als ongeldige waarde wordt opgegeven.
            - Logt de geselecteerde exercise_id voor debugging.
        """
        super().__init__(*args, **kwargs)
        from app.models import Exercise
        # Genereer keuzes: [(0, 'Selecteer een oefening'), (id, naam), ...]
        choices = [(0, 'Selecteer een oefening')] + [(e.id, e.name) for e in Exercise.query.all()]
        self.exercise_id.choices = choices
        # Valideer exercise_id en stel standaard in op 0 indien ongeldig
        if not self.exercise_id.data or self.exercise_id.data not in [c[0] for c in choices]:
            self.exercise_id.data = 0
        logger.debug(f"ExerciseForm initialized with exercise_id: {self.exercise_id.data}")

    class Meta:
        csrf = False  # Schakel CSRF uit voor subformulier binnen WorkoutPlanForm


class EditProfileForm(FlaskForm):
    """
    Formulier voor het bewerken van gebruikersprofielgegevens.
    Notities:
        - Valideert unieke naam in de database.
        - Gebruikt NumberRange voor realistische gewicht- en workout-waarden.
    """
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
        """
        Initialiseer het formulier met de oorspronkelijke gebruikersnaam.
        """
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        """
        Valideer dat de nieuwe naam uniek is in de database.
        Raises:
            ValidationError: Als de naam al in gebruik is door een andere gebruiker.
        """
        from app.models import User
        if name.data != self.original_name:
            user = User.query.filter_by(name=name.data).first()
            if user is not None:
                raise ValidationError('Please use a different name.')


class AddWeightForm(FlaskForm):
    """
    Formulier voor het toevoegen van een gewichtsmeting.
    Notities:
        - Gebruikt voor gewichtslogging in de gebruikersinterface.
        - NumberRange zorgt voor realistische gewichtswaarden.
        - Aangepaste validatie voorkomt niet-numerieke invoer.
    """
    weight = FloatField('Gewicht (kg)',
                       validators=[DataRequired(), NumberRange(min=20, max=300,
                       message="Gewicht moet tussen 20 en 300 kg zijn")])
    notes = TextAreaField('Notities (optioneel)',
                         validators=[Optional(), Length(max=200)])
    submit = SubmitField('Gewicht toevoegen')

    def validate_weight(self, weight):
        """
        Valideer dat het gewicht een geldige numerieke waarde is.
        Raises:
            ValidationError: Als de invoer geen geldige float is.
        """
        try:
            float(weight.data)
        except (ValueError, TypeError):
            logger.error(f"Invalid weight input: {weight.data}")
            raise ValidationError("Gewicht moet een geldig getal zijn (bijv. 70.5).")


class NameForm(FlaskForm):
    """
    Formulier voor het invoeren van de gebruikersnaam tijdens onboarding.
    Notities:
        - Eerste stap in de onboarding-flow.
        - Length-validator zorgt voor redelijke naamgrenzen.
    """
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('Next')


class CurrentWeightForm(FlaskForm):
    """
    Formulier voor het invoeren van het huidige gewicht tijdens onboarding.
    Notities:
        - Gebruikt RangeInput voor een interactieve invoer.
        - Geen expliciete validatie, afhankelijk van client-side range-attributen.
    """
    current_weight = FloatField('Current Weight', widget=RangeInput())
    submit = SubmitField('Next')


class GoalWeightForm(FlaskForm):
    """
    Formulier voor het invoeren van het doelgewicht tijdens onboarding.
    Notities:
        - Laatste stap in de onboarding-flow.
        - NumberRange zorgt voor realistische doelgewichten.
    """
    fitness_goal = FloatField('Streefgewicht (kg)', validators=[DataRequired(), NumberRange(min=30, max=500)])
    submit = SubmitField('Volgende')


class SearchExerciseForm(FlaskForm):
    """
    Formulier voor het zoeken van oefeningen met filters.
    Notities:
        - Ondersteunt geavanceerde filtering voor de oefeningbibliotheek.
        - Keuzes zijn gebaseerd op Enums uit models.py.
        - Lege keuzes ('') maken filters optioneel.
    """
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
    """
    Formulier voor het maken of bewerken van een workout-plan.
    Notities:
        - Gebruikt FieldList voor meerdere oefeningen.
        - Valideert unieke en geldige oefeningselecties.
        - Waarschuwt voor dubbele oefeningen via flash-bericht.
    """
    name = StringField('Plan Name', validators=[DataRequired(), Length(min=2, max=50)])
    exercises = FieldList(FormField(ExerciseForm), min_entries=0)
    submit = SubmitField('Create workout')

    def validate_exercises(self, field):
        """
        Valideer de lijst van oefeningen in het workout-plan.
        Notities:
            - Controleert of elke oefening een geldige exercise_id heeft (niet 0).
            - Logt exercise_ids voor debugging.
            - Geeft waarschuwing voor dubbele oefeningen via flash.
        """
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
    """
    Formulier voor het verwijderen van een workout-plan.
    Notities:
        - Leeg formulier, afhankelijk van CSRF-token en route-logica.
        - Gebruikt in acties waar alleen bevestiging nodig is.
    """
    pass


class DeleteExerciseForm(FlaskForm):
    """
    Formulier voor het verwijderen van een oefening uit een workout-plan.
    Notities:
        - Vereist een geldige waarde voor workout_plan_exercise_id.
        - Gebruikt in de workout-plan bewerkingsinterface.
    """
    workout_plan_exercise_id = IntegerField('Workout Plan Exercise ID', validators=[DataRequired()])
    submit = SubmitField('Delete')


class ActiveWorkoutForm(FlaskForm):
    """
    Formulier voor het activeren van een workout-plan.
    Notities:
        - Leeg formulier, afhankelijk van CSRF-token en route-logica.
        - Gebruikt om een plan als actief te markeren.
    """
    pass