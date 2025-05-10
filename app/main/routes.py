from flask import session, render_template, flash, redirect, url_for, request, current_app, jsonify
from app import db, oauth
from app.forms import EditProfileForm, SearchExerciseForm, WorkoutPlanForm, ExerciseLogForm
from app.models import User, Exercise, ExerciseMuscle, WorkoutPlan, WorkoutPlanExercise, ExerciseLog, exercise_muscle_association
from datetime import datetime, timezone
import sqlalchemy as sa
import logging
import secrets

#from fitness_app.app.models import exercise_muscle_association

logging.basicConfig(level=logging.DEBUG)

from app.main import bp

def get_current_user():
    if 'user' not in session:
        current_app.logger.debug("No user in session")
        return None
    user_info = session['user']['userinfo']
    sub = user_info.get('sub')
    if not sub:
        current_app.logger.error("No 'sub' in session user_info, forcing logout")
        session.clear()
        return None
    user = db.session.scalar(sa.select(User).where(User.sub == sub))
    if not user:
        current_app.logger.debug(f"User with sub {sub} not found in database")
    return user

@bp.context_processor
def inject_current_user():
    return dict(get_current_user=get_current_user)

@bp.before_request
def before_request():
    user = get_current_user()
    if user:
        user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        current_app.logger.debug('Rendering landings.html')
        return render_template('landings.html', title='Welcome to FitTrack', is_landing_page=True)
    user = get_current_user()
    if user is None:
        current_app.logger.error("User is None despite session, forcing logout")
        session.clear()
        return redirect(url_for('main.login'))
    form = SearchExerciseForm()
    exercises = []
    if form.validate_on_submit():
        query = form.query.data
        muscle = form.muscle.data
        level = form.level.data
        equipment = form.equipment.data
        filters = []
        if query:
            filters.append(Exercise.name.ilike(f'%{query}%'))
        if muscle:
            subquery = sa.select(exercise_muscle_association.c.exercise_id).where(
                exercise_muscle_association.c.muscle_id == (
                    sa.select(ExerciseMuscle.id).where(ExerciseMuscle.muscle == muscle)
                )
            )
            filters.append(Exercise.id.in_(subquery))
        if level:
            filters.append(Exercise.level == level)
        if equipment:
            filters.append(Exercise.equipment == equipment)
        exercises = db.session.execute(sa.select(Exercise).filter(*filters)).scalars().all()
    # Show user's recent plans and logs
    plans = db.paginate(
        sa.select(WorkoutPlan).where(WorkoutPlan.user_id == user.id).order_by(WorkoutPlan.created_at.desc()),
        page=1, per_page=5, error_out=False
    )
    logs = db.paginate(
        sa.select(ExerciseLog).where(ExerciseLog.user_id == user.id).order_by(ExerciseLog.completed_at.desc()),
        page=1, per_page=5, error_out=False
    )
    return render_template('index.html', title='Home', user=user, form=form, exercises=exercises,
                           plans=plans.items, logs=logs.items, is_landing_page=False)

@bp.route('/login')
def login():
    if 'user' in session:
        current_app.logger.debug("User already in session, redirecting to index")
        return redirect(url_for('main.index'))
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session.modified = True
    current_app.logger.debug(f"Generated OAuth state: {state}")
    redirect_uri = url_for('main.callback', _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri=redirect_uri, state=state)

@bp.route('/signup')
def signup():
    if 'user' in session:
        current_app.logger.debug("User already in session, redirecting to index")
        return redirect(url_for('main.index'))
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session.modified = True
    current_app.logger.debug(f"Generated OAuth state for signup: {state}")
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for('main.callback', _external=True),
        screen_hint='signup',
        state=state
    )

@bp.route('/callback')
def callback():
    try:
        received_state = request.args.get('state')
        expected_state = session.get('oauth_state')
        current_app.logger.debug(f"Received state: {received_state}, Expected state: {expected_state}")

        if not expected_state or received_state != expected_state:
            current_app.logger.error(f"State mismatch: received={received_state}, expected={expected_state}")
            session.pop('oauth_state', None)
            flash('Login failed due to state mismatch. Please try again.', 'danger')
            return redirect(url_for('main.login'))

        token = oauth.auth0.authorize_access_token()
        current_app.logger.debug(f"Token received: {token}")
        session['user'] = token
        user_info = token['userinfo']
        current_app.logger.debug(f"User info: {user_info}")

        sub = user_info.get('sub')
        if not sub:
            current_app.logger.error("No 'sub' found in user_info")
            session.pop('oauth_state', None)
            flash('Login failed: No user identifier provided.', 'danger')
            return redirect(url_for('main.login'))

        user = db.session.scalar(sa.select(User).where(User.sub == sub))
        if not user:
            username = user_info.get('nickname', user_info.get('email', sub.split('|')[-1]))
            email = user_info.get('email', '')
            user = User(
                username=username,
                email=email,
                sub=sub
            )
            db.session.add(user)
            db.session.commit()
            current_app.logger.debug(f"New user added: {user.username}, sub: {sub}")
        else:
            current_app.logger.debug(f"Existing user found: {user.username}, sub: {sub}")

        session['user']['id'] = user.id
        session.modified = True
        session.pop('oauth_state', None)
        current_app.logger.debug("Login successful")
        flash('You have been logged in!', 'success')
        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Error in callback: {str(e)}")
        session.pop('oauth_state', None)
        flash(f'Login failed: {str(e)}', 'danger')
        return redirect(url_for('main.login'))

@bp.route('/logout')
def logout():
    session.clear()
    current_app.logger.debug("Session cleared")
    return redirect(
        f"https://{current_app.config['AUTH0_DOMAIN']}/v2/logout?"
        f"client_id={current_app.config['AUTH0_CLIENT_ID']}&"
        f"returnTo={url_for('main.index', _external=True)}"
    )

@bp.route('/user/<username>')
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    page = request.args.get('page', 1, type=int)
    plans = db.paginate(
        sa.select(WorkoutPlan).where(WorkoutPlan.user_id == user.id).order_by(WorkoutPlan.created_at.desc()),
        page=page,
        per_page=10,
        error_out=False
    )
    logs = db.paginate(
        sa.select(ExerciseLog).where(ExerciseLog.user_id == user.id).order_by(ExerciseLog.completed_at.desc()),
        page=page,
        per_page=10,
        error_out=False
    )
    next_url = url_for('main.user', username=user.username, page=plans.next_num) if plans.has_next else None
    prev_url = url_for('main.user', username=user.username, page=plans.prev_num) if plans.has_prev else None
    return render_template('user.html', title=f'{user.username}\'s Profile', user=user,
                           plans=plans.items, logs=logs.items, next_url=next_url, prev_url=prev_url)

@bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user = get_current_user()
    if user is None:
        session.clear()
        return redirect(url_for('main.login'))
    form = EditProfileForm(user.username)
    if form.validate_on_submit():
        user.username = form.username.data
        user.fitness_goal = form.fitness_goal.data
        user.experience_level = form.experience_level.data
        user.current_weight = form.current_weight.data
        user.weekly_workouts = form.weekly_workouts.data
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('main.user', username=user.username))
    elif request.method == 'GET':
        form.username.data = user.username
        form.fitness_goal.data = user.fitness_goal
        form.experience_level.data = user.experience_level
        form.current_weight.data = user.current_weight
        form.weekly_workouts.data = user.weekly_workouts
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@bp.route('/create_plan', methods=['GET', 'POST'])
def create_plan():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user = get_current_user()
    if user is None:
        session.clear()
        return redirect(url_for('main.login'))
    form = WorkoutPlanForm()
    if form.validate_on_submit():
        plan = WorkoutPlan(
            user_id=user.id,
            name=form.name.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data
        )
        db.session.add(plan)
        db.session.commit()
        flash('Workout plan created successfully!')
        return redirect(url_for('main.user', username=user.username))
    return render_template('create_plan.html', title='Create Workout Plan', form=form)

@bp.route('/log_exercise', methods=['GET', 'POST'])
def log_exercise():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user = get_current_user()
    if user is None:
        session.clear()
        return redirect(url_for('main.login'))
    form = ExerciseLogForm()
    if form.validate_on_submit():
        log = ExerciseLog(
            user_id=user.id,
            exercise_id=form.exercise_id.data,
            workout_plan_id=form.workout_plan_id.data,
            completed=form.completed.data,
            sets=form.sets.data,
            reps=form.reps.data,
            weight=form.weight.data,
            duration=form.duration.data,
            notes=form.notes.data
        )
        db.session.add(log)
        db.session.commit()
        flash('Exercise logged successfully!')
        return redirect(url_for('main.user', username=user.username))
    return render_template('log_exercise.html', title='Log Exercise', form=form)