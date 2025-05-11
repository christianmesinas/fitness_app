# /app/app/main/routes.py
import logging
from datetime import datetime, timezone
from enum import Enum
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, oauth
from app.models import User, Exercise
from app.forms import EditProfileForm, NameForm, SearchExerciseForm, CurrentWeightForm, WorkoutPlanForm, \
    ExerciseLogForm, GoalWeightForm
from authlib.integrations.flask_client import OAuthError

main = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

class WorkoutFrequency(Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7

    @property
    def label(self):
        return f"{self.value} time{'s' if self.value > 1 else ''} per week"

@main.before_request
def before_request():
    try:
        if current_user.is_authenticated:
            current_user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
    except AttributeError as e:
        logger.error(f"Fout in before_request: {str(e)}")
        # Ga door zonder te crashen
        pass

@main.route('/test')
def test():
    return 'Test route working!'

@main.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    return render_template('landings.html')

@main.route('/index')
@login_required
def index():
    return render_template('index.html')

@main.route('/login')
def login():
    if current_user.is_authenticated:
        logger.debug("Gebruiker al ingelogd, redirect naar index")
        return redirect(url_for('main.index'))
    redirect_uri = url_for('main.callback', _external=True)
    try:
        if not hasattr(oauth, 'auth0'):
            logger.error("oauth.auth0 is niet geïnitialiseerd")
            raise AttributeError("Auth0 client is niet geïnitialiseerd")
        logger.debug(f"Start Auth0 login redirect naar {redirect_uri}")
        return oauth.auth0.authorize_redirect(redirect_uri)
    except Exception as e:
        logger.error(f"Fout in login route: {str(e)}", exc_info=True)
        flash('Authenticatie initiatie mislukt', 'danger')
        return redirect(url_for('main.landing'))

@main.route('/signup')
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    redirect_uri = url_for('main.callback', _external=True)
    try:
        if not hasattr(oauth, 'auth0'):
            logger.error("oauth.auth0 is niet geïnitialiseerd")
            raise AttributeError("Auth0 client is niet geïnitialiseerd")
        logger.debug(f"Start Auth0 signup redirect naar {redirect_uri} met screen_hint=signup")
        return oauth.auth0.authorize_redirect(redirect_uri, screen_hint='signup')
    except Exception as e:
        logger.error(f"Fout in signup route: {str(e)}", exc_info=True)
        flash('Authenticatie initiatie mislukt', 'danger')
        return redirect(url_for('main.landing'))

@main.route('/callback')
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        logger.debug(f"Token ontvangen: {token}")
        user_info = token.get('userinfo')
        logger.debug(f"Gebruiker info: {user_info}")

        if not user_info:
            logger.error("Geen gebruikersinformatie ontvangen van Auth0")
            flash('Authenticatie mislukt', 'danger')
            return redirect(url_for('main.landing'))

        sub = user_info.get('sub')
        user = db.session.scalar(db.select(User).where(User.sub == sub))
        if user is None:
            logger.debug(f"Gebruiker met sub {sub} niet gevonden in database")
            username = user_info.get('nickname', user_info.get('email').split('@')[0])
            base_username = username
            counter = 1
            while db.session.scalar(db.select(User).where(User.username == username)):
                username = f"{base_username}{counter}"
                counter += 1
            user_data = {
                'sub': sub,
                'email': user_info.get('email'),
                'username': username
            }
            if user_info.get('name'):
                user_data['name'] = user_info.get('name')
            if hasattr(User, 'registration_step'):
                user_data['registration_step'] = 'name'
            logger.debug(f"Maak nieuwe gebruiker aan met data: {user_data}")
            logger.debug(f"Gebruikte User klasse: {User}")
            user = User(**user_data)
            db.session.add(user)
            db.session.commit()
        else:
            logger.debug(f"Gebruiker met sub {sub} gevonden in database")

        if user is None:
            logger.error("Gebruiker is None ondanks sessie, forceer logout")
            logout_user()
            flash('Authenticatie mislukt', 'danger')
            return redirect(url_for('main.landing'))

        logger.debug(f"Probeer in te loggen met gebruiker: {user}")
        login_user(user)
        session['user'] = user_info
        if hasattr(user, 'registration_step') and user.registration_step != 'completed':
            logger.debug("Redirect naar onboarding_name")
            return redirect(url_for('main.onboarding_name'))
        logger.debug("Redirect naar index")
        return redirect(url_for('main.index'))

    except OAuthError as e:
        logger.error(f"OAuth fout in callback: {str(e)}")
        flash('Authenticatie mislukt', 'danger')
        return redirect(url_for('main.landing'))
    except Exception as e:
        logger.error(f"Fout in callback: {str(e)}", exc_info=True)
        flash('Authenticatie mislukt', 'danger')
        return redirect(url_for('main.landing'))


@main.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user', None)
    return redirect('https://dev-iwimqje37do0ovq5.us.auth0.com/v2/logout?' +
                    'client_id=0BvORaegNdDZmFlwiFrESSNXdrwPagxz&' +
                    'returnTo=' + url_for('main.landing', _external=True))

@main.route('/onboarding/name', methods=['GET', 'POST'])
@login_required
def onboarding_name():
    logger.debug(f"Toegang tot onboarding_name voor gebruiker: {current_user}")
    form = NameForm()
    if form.validate_on_submit():
        logger.debug("Formulier succesvol gevalideerd")
        current_user.name = form.name.data
        current_user.registration_step = 'current_weight'
        try:
            db.session.commit()
            logger.debug("Gebruikersnaam opgeslagen, redirect naar onboarding_current_weight")
            return redirect(url_for('main.onboarding_current_weight'))
        except Exception as e:
            logger.error(f"Fout bij database commit: {str(e)}")
            db.session.rollback()
            flash('Er is een fout opgetreden bij het opslaan van je naam.', 'danger')
    else:
        if form.errors:
            logger.debug(f"Formulier validatiefouten: {form.errors}")
    return render_template('Q-name.html', form=form)


@main.route('/onboarding/workout', methods=['GET', 'POST'])
@login_required
def onboarding_workout():
    if request.method == 'POST':
        workout = request.form.get('workout')
        try:
            current_user.weekly_workouts = int(workout)
            current_user.registration_step = 'current_weight'
            db.session.commit()
            return redirect(url_for('main.onboarding_current_weight'))
        except ValueError:
            flash('Please select a valid workout frequency', 'danger')
    return render_template('Q-workouts.html', workout_frequencies=WorkoutFrequency)

@main.route('/onboarding/current_weight', methods=['GET', 'POST'])
@login_required
def onboarding_current_weight():
    logger.debug(f"Toegang tot onboarding_current_weight voor gebruiker: {current_user}")
    form = CurrentWeightForm()
    if form.validate_on_submit():
        logger.debug("Formulier succesvol gevalideerd")
        current_user.current_weight = form.current_weight.data
        current_user.registration_step = 'goal_weight'
        try:
            db.session.commit()
            logger.debug("Huidig gewicht opgeslagen, redirect naar onboarding_goal_weight")
            return redirect(url_for('main.onboarding_goal_weight'))
        except Exception as e:
            logger.error(f"Fout bij database commit: {str(e)}")
            db.session.rollback()
            flash('Er is een fout opgetreden bij het opslaan van je gewicht.', 'danger')
    else:
        if form.errors:
            logger.debug(f"Formulier validatiefouten: {form.errors}")
    return render_template('Q-current-weight.html', form=form)


@main.route('/onboarding/goal_weight', methods=['GET', 'POST'])
@login_required
def onboarding_goal_weight():
    logger.debug(f"Toegang tot onboarding_goal_weight voor gebruiker: {current_user}")
    form = GoalWeightForm()
    if form.validate_on_submit():
        logger.debug("Formulier succesvol gevalideerd")
        current_user.fitness_goal = form.fitness_goal.data
        current_user.registration_step = 'workouts'
        try:
            db.session.commit()
            logger.debug("Ideaal gewicht opgeslagen, redirect naar onboarding_workout")
            return redirect(url_for('main.onboarding_workout'))
        except Exception as e:
            logger.error(f"Fout bij database commit: {str(e)}")
            db.session.rollback()
            flash('Er is een fout opgetreden bij het opslaan van je ideale gewicht.', 'danger')
    else:
        if form.errors:
            logger.debug(f"Formulier validatiefouten: {form.errors}")
    return render_template('Q-ideal-weight.html', form=form)



@main.route('/user/<user>')
@login_required
def user(user):
    user_obj = db.session.scalar(db.select(User).where(User.username == user))
    if user_obj is None:
        flash('User not found', 'danger')
        return redirect(url_for('main.index'))
    return render_template('user.html', user=user_obj)

@main.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.user)
    if form.validate_on_submit():
        current_user.user = form.user.data
        current_user.current_weight = form.current_weight.data
        current_user.weekly_workouts = form.weekly_workouts.data
        db.session.commit()
        flash('Your profile has been updated', 'success')
        return redirect(url_for('main.user', user=current_user.user))
    elif request.method == 'GET':
        form.user.data = current_user.user
        form.current_weight.data = current_user.current_weight
        form.weekly_workouts.data = current_user.weekly_workouts
    return render_template('edit_profile.html', form=form)

@main.route('/search_exercise', methods=['GET', 'POST'])
@login_required
def search_exercise():
    form = SearchExerciseForm()
    exercises = []
    if form.validate_on_submit():
        search_term = form.search_term.data
        exercises = db.session.scalars(
            db.select(Exercise).where(Exercise.name.ilike(f'%{search_term}%'))
        ).all()
    return render_template('search_exercise.html', form=form, exercises=exercises)

@main.route('/create_plan', methods=['GET', 'POST'])
@login_required
def create_plan():
    form = WorkoutPlanForm()
    if form.validate_on_submit():
        plan = WorkoutPlan(
            user_id=current_user.id,
            name=form.name.data
        )
        db.session.add(plan)
        for exercise_form in form.exercises:
            exercise = WorkoutPlanExercise(
                exercise_id=exercise_form.exercise_id.data,
                sets=exercise_form.sets.data,
                reps=exercise_form.reps.data,
                weight=exercise_form.weight.data
            )
            plan.exercises.append(exercise)
        db.session.commit()
        flash('Workout plan created', 'success')
        return redirect(url_for('main.index'))
    return render_template('create_plan.html', form=form)

@main.route('/log_exercise', methods=['GET', 'POST'])
@login_required
def log_exercise():
    form = ExerciseLogForm()
    if form.validate_on_submit():
        log = ExerciseLog(
            user_id=current_user.id,
            exercise_id=form.exercise_id.data,
            sets=form.sets.data,
            reps=form.reps.data,
            weight=form.weight.data
        )
        db.session.add(log)
        db.session.commit()
        flash('Exercise logged', 'success')
        return redirect(url_for('main.index'))
    return render_template('log_exercise.html', form=form)