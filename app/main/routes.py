from flask import render_template, flash, redirect, url_for, request, session, current_app
from flask_login import login_required, current_user, login_user
from app.forms import EditProfileForm, NameForm, SearchExerciseForm, CurrentWeightForm, WorkoutPlanForm, \
    ExerciseLogForm, GoalWeightForm
from app.models import Exercise, ExerciseMuscle
from authlib.integrations.flask_client import OAuthError
import logging
from datetime import datetime, timezone
from sqlalchemy import or_


from .utils import check_onboarding_status, fix_image_path
from .. import db
from ..models import User

logger = logging.getLogger(__name__)
logger.debug("Start van routes.py")

# De blueprint wordt geïmporteerd vanuit main/__init__.py
from . import bp as main

logger.debug("Main blueprint geïmporteerd in routes.py")

@main.route('/test')
def test():
    logger.debug("Test route aangeroepen")
    return 'Test route working!'

@main.route('/')
def landing():
    logger.debug(f"Landing route, is_authenticated: {current_user.is_authenticated}, session: {session.get('_user_id')}")
    if current_user.is_authenticated:
        logger.debug(f"Gebruiker ingelogd: {current_user.name}")
        return redirect(url_for('main.index'))
    try:
        logger.debug("Probeer landings.html te renderen")
        return render_template('landings.html', is_landing_page=True)
    except Exception as e:
        logger.error(f"Fout bij renderen van landings.html: {str(e)}", exc_info=True)
        raise

@main.route('/index')
@login_required
def index():
    logger.debug(f"Index route aangeroepen voor {current_user.name}")
    # Controleer onboarding-status
    onboarding_redirect = check_onboarding_status(current_user)
    if onboarding_redirect:
        logger.debug(f"Redirect naar onboarding-stap: {onboarding_redirect}")
        return redirect(onboarding_redirect)

    return render_template('index.html')


@main.route('/login')
def login():
    logger.debug("Login route aangeroepen")
    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.name}")
        return redirect(url_for('main.index'))
    try:
        from app import oauth  # Lazy import
        redirect_response = oauth.auth0.authorize_redirect(redirect_uri=url_for('main.callback', _external=True))
        logger.debug(f"Auth0 login redirect URL: {redirect_response.location}")
        return redirect_response
    except Exception as e:
        logger.error(f"Auth0 login fout: {str(e)}")
        flash('Fout bij inloggen. Probeer opnieuw.')
        return redirect(url_for('main.landing'))

@main.route('/signup')
def signup():
    logger.debug("Signup route aangeroepen")
    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.name}")
        return redirect(url_for('main.index'))
    try:
        from app import oauth  # Lazy import
        redirect_response = oauth.auth0.authorize_redirect(
            redirect_uri=url_for('main.callback', _external=True),
            screen_hint='signup'
        )
        logger.debug(f"Auth0 signup redirect URL: {redirect_response.location}")
        return redirect_response
    except Exception as e:
        logger.error(f"Auth0 signup fout: {str(e)}")
        flash('Fout bij aanmelden. Probeer opnieuw.')
        return redirect(url_for('main.landing'))

from flask import redirect, url_for, session, flash
import logging

logger = logging.getLogger(__name__)
logger.debug("Start van routes.py")


@main.route('/callback')
def callback():
    try:
        from app import oauth, db
        token = oauth.auth0.authorize_access_token()
        if not token:
            logger.error("Geen toegangstoken ontvangen van Auth0.")
            flash('Authenticatie mislukt.')
            return redirect(url_for('main.landing'))

        userinfo = oauth.auth0.get(f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo").json()

        user = User.query.filter_by(email=userinfo['email']).first()
        if not user:
            user = User(
                email=userinfo['email'],
                auth0_id=userinfo['sub'],
            )
            db.session.add(user)
            db.session.commit()

        login_user(user)
        logger.debug(f"User ingelogd: id={user.get_id()}, name={user.name}")

        session['new_user'] = False  # je kan ook hier checken

        onboarding_redirect = check_onboarding_status(user)
        if onboarding_redirect:
            return redirect(onboarding_redirect)

        return redirect(url_for('main.index'))
    except Exception as e:
        logger.error(f"Callback fout: {e}")
        flash('Authenticatie mislukt. Probeer opnieuw.')
        return redirect(url_for('main.landing'))


@main.route('/logout')
@login_required
def logout():
    logger.debug(f"Logout route, user: {current_user.name}")
    from flask_login import logout_user
    logout_user()
    session.clear()
    return redirect('https://' + current_app.config['AUTH0_DOMAIN'] +
                    '/v2/logout?client_id=' + current_app.config['AUTH0_CLIENT_ID'] +
                    '&returnTo=' + url_for('main.landing', _external=True))

@main.route('/onboarding/name', methods=['GET', 'POST'])
def onboarding_name():
    user = current_user

    # Maak een formulier aan
    form = NameForm()

    if form.validate_on_submit():
        # Update de naam van de gebruiker in de database
        user.name = form.name.data
        db.session.commit()

        # Redirect naar de volgende onboarding stap
        return redirect(url_for('main.onboarding_current_weight'))

    return render_template('onboarding_name.html', form=form, user=user)


@main.route('/onboarding/current_weight', methods=['GET', 'POST'])
@login_required
def onboarding_current_weight():
    form = CurrentWeightForm()
    from app import db  # Lazy import
    if form.validate_on_submit():
        current_user.current_weight = form.current_weight.data
        db.session.commit()
        logger.debug(f"Onboarding huidig gewicht voltooid voor {current_user.name}, huidig gewicht: {current_user.current_weight}")
        return redirect(url_for('main.onboarding_goal_weight'))
    return render_template('onboarding_current_weight.html', form=form)

@main.route('/onboarding/goal_weight', methods=['GET', 'POST'])
@login_required
def onboarding_goal_weight():
    form = GoalWeightForm()
    if form.validate_on_submit():
        current_user.fitness_goal = form.fitness_goal.data
        db.session.commit()

        # Doorsturen naar volgende onboarding-stap
        onboarding_redirect = check_onboarding_status(current_user)
        if onboarding_redirect:
            return redirect(onboarding_redirect)

        return redirect(url_for('main.index'))

    return render_template(
        'onboarding_goal_weight.html',
        form=form,
        user=current_user
    )


@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    logger.debug(f"Profile route, user: {current_user.name}")
    from app import db  # Lazy import
    form = EditProfileForm(current_user.name)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.current_weight = form.current_weight.data
        current_user.weekly_workouts = form.weekly_workouts.data
        db.session.commit()
        logger.debug(f"Profiel bijgewerkt: {current_user.name}")
        flash('Je profiel is bijgewerkt!')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.name.data = current_user.name
        form.current_weight.data = current_user.current_weight
        form.weekly_workouts.data = current_user.weekly_workouts
    return render_template('user.html', user=current_user)

@main.route('/add_workout')
@login_required
def add_workout():
    logger.debug(f"Add workout page geopend door {current_user.name}")
    return render_template('add_workout.html')

@main.route('/search_exercise', methods=['GET', 'POST'])
@login_required
def search_exercise():
    logger.debug(f"Search exercise route called by: {current_user.name}")
    form = SearchExerciseForm()
    exercises = []

    if form.validate_on_submit():
        search_term = form.search_term.data.strip() if form.search_term.data else ""
        difficulty = form.difficulty.data
        muscle_group = form.muscle_group.data
        exercise_type = form.exercise_type.data

        query = Exercise.query
        if search_term:
            query = query.filter(Exercise.name.ilike(f'%{search_term}%'))
        if difficulty:
            level_map = {"easy": "beginner", "medium": "intermediate", "hard": "expert"}
            level = level_map.get(difficulty)
            if level:
                query = query.filter(Exercise.level == level)
        if muscle_group:
            query = query.join(Exercise.primary_muscles).filter(ExerciseMuscle.muscle == muscle_group)
        if exercise_type:
            query = query.filter(Exercise.equipment == exercise_type)

        exercises = query.limit(25).all()

        if not exercises and (search_term or difficulty or muscle_group or exercise_type):
            flash('Geen oefeningen gevonden. Probeer andere filters.')
    else:
        # Handle GET request with query parameters
        search_term = request.args.get('search_term', '').strip()
        difficulty = request.args.get('difficulty', '')
        muscle_group = request.args.get('muscle_group', '')
        exercise_type = request.args.get('exercise_type', '')

        query = Exercise.query
        if search_term:
            query = query.filter(Exercise.name.ilike(f'%{search_term}%'))
        if difficulty:
            level_map = {"easy": "beginner", "medium": "intermediate", "hard": "expert"}
            level = level_map.get(difficulty)
            if level:
                query = query.filter(Exercise.level == level)
        if muscle_group:
            query = query.join(Exercise.primary_muscles).filter(ExerciseMuscle.muscle == muscle_group)
        if exercise_type:
            query = query.filter(Exercise.equipment == exercise_type)

        exercises = query.limit(25).all()

    exercises_dict = [ex.to_dict() for ex in exercises]
    for ex in exercises_dict:
        if ex.get('images'):
            ex['images'] = [fix_image_path(img) for img in ex['images']]

        logger.debug(f"Exercise: {ex['name']}, Images: {ex['images']}")
    return render_template('search_exercise.html', form=form, exercises=exercises_dict)

@main.route('/create_workout_plan', methods=['GET', 'POST'])
@login_required
def create_workout_plan():
    logger.debug(f"Create workout plan route, user: {current_user.name}")
    from app import db  # Lazy import
    form = WorkoutPlanForm()
    if form.validate_on_submit():
        from app.models import WorkoutPlan, WorkoutPlanExercise
        plan = WorkoutPlan(name=form.name.data, user_id=current_user.id)
        db.session.add(plan)
        db.session.flush()
        for exercise_form in form.exercises:
            plan_exercise = WorkoutPlanExercise(
                workout_plan_id=plan.id,
                exercise_id=exercise_form.exercise_id.data,
                sets=exercise_form.sets.data,
                reps=exercise_form.reps.data,
                weight=exercise_form.weight.data
            )
            db.session.add(plan_exercise)
        db.session.commit()
        logger.debug(f"Workout plan aangemaakt: {plan.name}")
        flash('Workout plan aangemaakt!')
        return redirect(url_for('main.index'))
    return render_template('create_workout_plan.html', form=form)

@main.route('/log_exercise', methods=['GET', 'POST'])
@login_required
def log_exercise():
    logger.debug(f"Log exercise route, user: {current_user.name}")
    from app import db  # Lazy import
    form = ExerciseLogForm()
    if form.validate_on_submit():
        from app.models import ExerciseLog
        log = ExerciseLog(
            user_id=current_user.id,
            exercise_id=form.exercise_id.data,
            sets=form.sets.data,
            reps=form.reps.data,
            weight=form.weight.data,
            date=datetime.now(timezone.utc)
        )
        db.session.add(log)
        db.session.commit()
        logger.debug(f"Oefening gelogd: {form.exercise_id.data}")
        flash('Oefening gelogd!')
        return redirect(url_for('main.index'))
    return render_template('log_exercise.html', form=form)