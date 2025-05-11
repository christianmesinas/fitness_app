from flask import render_template, flash, redirect, url_for, request, session, current_app
from flask_login import login_required, current_user
from app.forms import EditProfileForm, NameForm, SearchExerciseForm, CurrentWeightForm, WorkoutPlanForm, \
    ExerciseLogForm, GoalWeightForm
from authlib.integrations.flask_client import OAuthError
import logging
from datetime import datetime, timezone

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
        logger.debug(f"Gebruiker ingelogd: {current_user.username}")
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
    logger.debug(f"Index route, user: {current_user.username}, is_authenticated: {current_user.is_authenticated}")
    return render_template('index.html', title='Home')

@main.route('/login')
def login():
    logger.debug("Login route aangeroepen")
    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.username}")
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
        logger.debug(f"Gebruiker al ingelogd: {current_user.username}")
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

@main.route('/callback')
def callback():
    logger.debug("Callback route aangeroepen")
    try:
        from app import oauth, db  # Lazy import
        token = oauth.auth0.authorize_access_token()
        # Gebruik de volledige userinfo endpoint URL
        userinfo = oauth.auth0.get(f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo").json()
        logger.debug(f"Userinfo ontvangen: {userinfo}")

        from app.models import User
        with current_app.app_context():
            user = User.query.filter_by(email=userinfo['email']).first()
            is_new_user = False
            if not user:
                user = User(
                    username=userinfo.get('nickname', userinfo['email'].split('@')[0]),
                    email=userinfo['email'],
                    auth0_id=userinfo['sub']
                )
                db.session.add(user)
                db.session.commit()
                logger.debug(f"Nieuwe gebruiker aangemaakt: {user.username}")
                is_new_user = True
            else:
                logger.debug(f"Bestaande gebruiker: {user.username}")

            from flask_login import login_user
            login_user(user)
            logger.debug(f"Gebruiker ingelogd: {user.username}")
            session['new_user'] = is_new_user
            logger.debug(f"Session new_user ingesteld: {session['new_user']}")

            if session.get('new_user'):
                logger.debug("Redirect naar onboarding/name")
                return redirect(url_for('main.onboarding_name'))
            logger.debug("Redirect naar index")
            return redirect(url_for('main.index'))
    except OAuthError as e:
        logger.error(f"OAuth fout in callback: {str(e)}")
        flash('Authenticatie mislukt. Probeer opnieuw.')
        return redirect(url_for('main.landing'))
    except Exception as e:
        logger.error(f"Fout in callback: {str(e)}", exc_info=True)
        return redirect(url_for('main.landing'))

@main.route('/logout')
@login_required
def logout():
    logger.debug(f"Logout route, user: {current_user.username}")
    from flask_login import logout_user
    logout_user()
    session.clear()
    return redirect('https://' + current_app.config['AUTH0_DOMAIN'] +
                    '/v2/logout?client_id=' + current_app.config['AUTH0_CLIENT_ID'] +
                    '&returnTo=' + url_for('main.landing', _external=True))

@main.route('/onboarding/name', methods=['GET', 'POST'])
@login_required
def onboarding_name():
    logger.debug(f"Onboarding name route, user: {current_user.username}")
    if not session.get('new_user'):
        return redirect(url_for('main.index'))
    from app import db  # Lazy import
    form = NameForm()
    if form.validate_on_submit():
        current_user.username = form.name.data
        db.session.commit()
        logger.debug(f"Gebruikersnaam bijgewerkt: {current_user.username}")
        return redirect(url_for('main.onboarding_current_weight'))
    return render_template('onboarding_name.html', form=form)

@main.route('/onboarding/current_weight', methods=['GET', 'POST'])
@login_required
def onboarding_current_weight():
    logger.debug(f"Onboarding current weight route, user: {current_user.username}")
    if not session.get('new_user'):
        return redirect(url_for('main.index'))
    from app import db  # Lazy import
    form = CurrentWeightForm()
    if form.validate_on_submit():
        current_user.current_weight = form.current_weight.data
        current_user.weight_updated = datetime.now(timezone.utc)
        db.session.commit()
        logger.debug(f"Huidig gewicht bijgewerkt: {current_user.current_weight}")
        return redirect(url_for('main.onboarding_goal_weight'))
    return render_template('onboarding_current_weight.html', form=form)

@main.route('/onboarding/goal_weight', methods=['GET', 'POST'])
@login_required
def onboarding_goal_weight():
    logger.debug(f"Onboarding goal weight route, user: {current_user.username}")
    if not session.get('new_user'):
        return redirect(url_for('main.index'))
    from app import db  # Lazy import
    form = GoalWeightForm()
    if form.validate_on_submit():
        current_user.fitness_goal = form.fitness_goal.data
        db.session.commit()
        logger.debug(f"Fitness doel bijgewerkt: {current_user.fitness_goal}")
        session.pop('new_user', None)
        return redirect(url_for('main.index'))
    return render_template('onboarding_goal_weight.html', form=form)

@main.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    logger.debug(f"Profile route, user: {current_user.username}")
    from app import db  # Lazy import
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.current_weight = form.current_weight.data
        current_user.weekly_workouts = form.weekly_workouts.data
        db.session.commit()
        logger.debug(f"Profiel bijgewerkt: {current_user.username}")
        flash('Je profiel is bijgewerkt!')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.current_weight.data = current_user.current_weight
        form.weekly_workouts.data = current_user.weekly_workouts
    return render_template('profile.html', form=form)

@main.route('/search_exercise', methods=['GET', 'POST'])
@login_required
def search_exercise():
    logger.debug(f"Search exercise route, user: {current_user.username}")
    from app import db  # Lazy import
    form = SearchExerciseForm()
    exercises = []
    if form.validate_on_submit():
        search_term = form.search_term.data
        from app.models import Exercise
        exercises = Exercise.query.filter(
            Exercise.name.ilike(f'%{search_term}%') |
            Exercise.description.ilike(f'%{search_term}%')
        ).all()
        logger.debug(f"Oefeningen gevonden: {len(exercises)}")
    return render_template('search_exercise.html', form=form, exercises=exercises)

@main.route('/create_workout_plan', methods=['GET', 'POST'])
@login_required
def create_workout_plan():
    logger.debug(f"Create workout plan route, user: {current_user.username}")
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
    logger.debug(f"Log exercise route, user: {current_user.username}")
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