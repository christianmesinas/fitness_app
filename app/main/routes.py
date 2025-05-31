from authlib.integrations.flask_oauth2 import requests
from flask import render_template, request, current_app, session, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user, login_user, logout_user
from app.forms import EditProfileForm, NameForm, SearchExerciseForm, CurrentWeightForm, WorkoutPlanForm, \
    ExerciseLogForm, GoalWeightForm, ExerciseForm, SimpleWorkoutPlanForm, DeleteWorkoutForm, DeleteExerciseForm
from app.models import Exercise, WorkoutPlanExercise, WorkoutPlan, ExerciseLog
import logging
from flask_wtf.csrf import CSRFError
from datetime import datetime, timezone
from sqlalchemy import select

import json


from .utils import check_onboarding_status, fix_image_path, clean_instruction_text
from .. import db
from ..models import User

logger = logging.getLogger(__name__)
logger.debug("Start van routes.py")

logging.basicConfig(level=logging.DEBUG)


# De blueprint wordt geïmporteerd vanuit main/__init__.py
from . import bp as main

logger.debug("Main blueprint geïmporteerd in routes.py")

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

    workout_plans = WorkoutPlan.query.filter_by(user_id=current_user.id).all()

    workout_data = []
    for plan in workout_plans:
        exercises = plan.exercises.order_by(WorkoutPlanExercise.order).all()  # lijst van WorkoutPlanExercise objecten
        # Haal de oefening-objecten eruit
        exercise_objs = [entry.exercise for entry in exercises]
        workout_data.append({
            'plan': plan,
            'exercises': exercise_objs
        })

    delete_form = DeleteWorkoutForm()

    return render_template('index.html', workout_data=workout_data, delete_form=delete_form)

@main.route('/login')
def login():
    logger.debug("Login route aangeroepen")

    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.name} — uitloggen voor login")
        logout_user()
        session.clear()

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
        logger.debug(f"Gebruiker al ingelogd: {current_user.name} — uitloggen voor signup")
        logout_user()
        session.clear()

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


@main.route('/add_exercise_to_plan/<int:plan_id>', methods=['POST'])
@login_required
def add_exercise_to_plan(plan_id):
    data = request.get_json()
    if not data or 'exercise_id' not in data:
        logger.error(f"Missing exercise_id in request: {data}")
        return jsonify({'success': False, 'message': 'Exercise ID is required'}), 400

    try:
        exercise_id = int(data['exercise_id'])
    except (ValueError, TypeError):
        logger.error(f"Invalid exercise_id: {data.get('exercise_id')}")
        return jsonify({'success': False, 'message': 'Invalid exercise ID'}), 400

    next_url = data.get('next') or url_for('main.edit_workout', plan_id=plan_id)

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        logger.error(f"Unauthorized access: user={current_user.id}, plan_user={workout_plan.user_id}")
        return jsonify({'success': False, 'message': 'Unauthorized access to workout plan'}), 403

    exercise = Exercise.query.get(exercise_id)
    if not exercise:
        logger.error(f"Exercise not found: exercise_id={exercise_id}")
        return jsonify({'success': False, 'message': 'Exercise not found'}), 404

    # Check for duplicates
    existing = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
    if existing:
        logger.debug(f"Duplicate exercise: plan_id={plan_id}, exercise_id={exercise_id}")
        return jsonify({'success': False, 'message': 'Exercise already in workout plan'}), 400

    # Determine next order
    max_order = db.session.query(db.func.max(WorkoutPlanExercise.order)).filter_by(workout_plan_id=plan_id).scalar() or -1
    next_order = max_order + 1

    new_exercise = WorkoutPlanExercise(
        workout_plan_id=plan_id,
        exercise_id=exercise_id,
        sets=3,
        reps=10,
        weight=0.0,  # Changed to 0.0 to match /add_exercise
        order=next_order
    )
    db.session.add(new_exercise)

    try:
        db.session.commit()
        logger.debug(f"Exercise added: plan_id={plan_id}, exercise_id={exercise_id}, exercise_name={exercise.name}")
        return jsonify({'success': True, 'message': f'{exercise.name} added to workout plan', 'redirect': next_url})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to add exercise: {str(e)}")
        return jsonify({'success': False, 'message': 'Error adding exercise'}), 500



@main.route('/add_workout', methods=['GET', 'POST'])
@login_required
def add_workout():
    logger.debug(f"Add workout route, user: {current_user.name}, user_id: {current_user.id}")
    form = WorkoutPlanForm()

    if form.validate_on_submit():
        new_workout = WorkoutPlan(name=form.name.data, user_id=current_user.id)
        db.session.add(new_workout)
        db.session.flush()  # Ensure new_workout.id is available

        # Add exercises from form
        for index, exercise_form in enumerate(form.exercises):
            plan_exercise = WorkoutPlanExercise(
                workout_plan_id=new_workout.id,
                exercise_id=exercise_form.exercise_id.data,
                sets=exercise_form.sets.data,
                reps=exercise_form.reps.data,
                weight=exercise_form.weight.data,
                order=index
            )
            db.session.add(plan_exercise)

        # Add exercises from session
        temp_exercises = session.get('temp_exercises', [])
        logger.debug(f"Saving temp_exercises: {temp_exercises}")
        for index, exercise_id in enumerate(temp_exercises, start=len(form.exercises)):
            plan_exercise = WorkoutPlanExercise(
                workout_plan_id=new_workout.id,
                exercise_id=exercise_id,
                sets=3,
                reps=10,
                weight=0.0,
                order=index
            )
            db.session.add(plan_exercise)

        current_user.current_workout_plan = new_workout

        db.session.commit()
        session.pop('temp_exercises', None)
        flash("Workout aangemaakt!", "success")
        return redirect(url_for('main.edit_workout', plan_id=new_workout.id))

    # For GET request: load temporary exercises from session
    temp_exercises = session.get('temp_exercises', [])
    logger.debug(f"Loading temp_exercises: {temp_exercises}")
    exercises = db.session.scalars(
        select(Exercise).filter(Exercise.id.in_(temp_exercises))
    ).all() if temp_exercises else []

    existing_plans = WorkoutPlan.query.filter_by(user_id=current_user.id).order_by(WorkoutPlan.created_at.desc()).all()


    return render_template('new_workout.html', form=form, plan=None, workout_plan=None, exercises=exercises, existing_plans=existing_plans)

import json

@main.route('/edit_workout/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def edit_workout(plan_id):
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    delete_exercise_form = DeleteExerciseForm()

    if workout_plan.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout.", "error")
        logger.debug(f"User {current_user.id} attempted to access plan_id {plan_id}")
        return redirect(url_for('main.index'))

    # Initialize form
    form = WorkoutPlanForm(obj=workout_plan)
    logger.debug(f"Initial form.name.data: {form.name.data}, workout_plan.name: {workout_plan.name}")

    if request.method == 'GET':
        # Clear existing entries
        while form.exercises.entries:
            form.exercises.pop_entry()
        # Populate form.exercises with existing exercises
        plan_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()
        for plan_exercise in plan_exercises:
            exercise_form = ExerciseForm()
            logger.debug(f"Populating exercise_form with exercise_id: {plan_exercise.exercise_id}")
            exercise_form.exercise_id.data = plan_exercise.exercise_id
            exercise_form.sets.data = plan_exercise.sets
            exercise_form.reps.data = plan_exercise.reps
            exercise_form.weight.data = plan_exercise.weight
            exercise_form.order.data = plan_exercise.order or 0
            form.exercises.append_entry(exercise_form)

    # Convert image strings to list
    exercises = Exercise.query.all()
    for ex in exercises:
        try:
            ex.images_list = json.loads(ex.images) if ex.images else []
            logger.debug(f"Exercise {ex.id}: images_list = {ex.images_list}")
        except Exception:
            ex.images_list = []
            logger.error(f"Failed to parse images for exercise {ex.id}")
    exercises_dict = {str(ex.id): ex for ex in exercises}

    if request.method == 'POST':
        logger.debug(f"POST data: {request.form}")
        # Log all exercise_ids in form
        for idx, exercise_form in enumerate(form.exercises):
            logger.debug(f"Form exercise {idx}: exercise_id={exercise_form.exercise_id.data}")

    if form.validate_on_submit():
        logger.debug(f"Form submitted, form.name.data: {form.name.data}, form.exercises.data: {form.exercises.data}")
        # Update workout_plan name
        workout_plan.name = form.name.data
        db.session.add(workout_plan)

        # Delete existing WorkoutPlanExercise records
        WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).delete()

        # Add updated exercises
        for idx, exercise_form in enumerate(form.exercises):
            logger.debug(f"Saving exercise with exercise_id: {exercise_form.exercise_id.data}")
            plan_exercise = WorkoutPlanExercise(
                workout_plan_id=workout_plan.id,
                exercise_id=exercise_form.exercise_id.data,
                sets=exercise_form.sets.data or 0,
                reps=exercise_form.reps.data or 0,
                weight=exercise_form.weight.data or 0.0,
                order=idx
            )
            db.session.add(plan_exercise)

        try:
            db.session.commit()
            flash('Workout bijgewerkt!', 'success')
            logger.debug(f"Workout updated, new name: {workout_plan.name}")
        except Exception as e:
            db.session.rollback()
            flash('Er is iets fout gegaan bij het opslaan.', 'error')
            logger.error(f"Database commit failed: {str(e)}")

        return redirect(url_for('main.edit_workout', plan_id=plan_id))
    else:
        if request.method == 'POST':
            logger.error(f"Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Fout in {field}: {error}", 'error')

    plan_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()
    exercise_pairs = [(pe, form.exercises.entries[i]) for i, pe in enumerate(plan_exercises)]
    logger.debug(f"exercise_pairs length: {len(exercise_pairs)}, plan_exercises length: {len(plan_exercises)}, form.exercises.entries length: {len(form.exercises.entries)}")


#ik heb nu mijn template als dit ik kan de naam nu wijzigen maar als ik 1 oefening verwijder van de workout verandert alle exercises naar deze met id 1 en de eerste toegevoegde oefening kan ik hier dan niet verwijderen

    return render_template(
        'edit_workout.html',
        form=form,
        workout_plan=workout_plan,
        exercises_dict=exercises_dict,
        delete_exercise_form=delete_exercise_form,
        exercise_pairs=exercise_pairs
    )

@main.route('/delete_exercise_from_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_exercise_from_plan(plan_id):
    form = DeleteExerciseForm()
    if form.validate_on_submit():
        try:
            wpe_id = int(form.workout_plan_exercise_id.data)
        except (ValueError, TypeError):
            flash("Ongeldig item ID.", "error")
            return redirect(url_for('main.edit_workout', plan_id=plan_id))

        wpe = WorkoutPlanExercise.query.get_or_404(wpe_id)

        if wpe.workout_plan_id != plan_id:
            flash("Deze oefening hoort niet bij dit plan.", "error")
            return redirect(url_for('main.edit_workout', plan_id=plan_id))

        # Check eigenaar van plan
        workout_plan = WorkoutPlan.query.get_or_404(plan_id)
        if workout_plan.user_id != current_user.id:
            flash("Geen toegang tot dit plan.", "error")
            return redirect(url_for('main.index'))

        db.session.delete(wpe)
        db.session.commit()
        flash("Oefening verwijderd.", "success")
    else:
        flash("Ongeldig formulier.", "error")

    return redirect(url_for('main.edit_workout', plan_id=plan_id))





@main.route('/add_exercise/<int:plan_id>/<int:exercise_id>', methods=['POST'])
@login_required
def add_exercise(plan_id, exercise_id):
    logger.debug(f"Add exercise: user={current_user.name}, user_id={current_user.id}, plan_id={plan_id}, exercise_id={exercise_id}, request_data={request.get_json()}, csrf_token={request.headers.get('X-CSRF-Token')}")

    try:
        if plan_id == 0:
            # Store exercise in session for new workouts
            if 'temp_exercises' not in session:
                session['temp_exercises'] = []
            if exercise_id not in session['temp_exercises']:
                session['temp_exercises'].append(exercise_id)
                session.modified = True
                logger.debug(f"Added exercise_id={exercise_id} to session: {session['temp_exercises']}")
            else:
                logger.debug(f"Exercise_id={exercise_id} already in session")
            return jsonify({'success': True, 'message': 'Exercise added to temporary workout'})

        workout_plan = WorkoutPlan.query.get(plan_id)
        if not workout_plan:
            logger.error(f"Workout plan not found: plan_id={plan_id}")
            return jsonify({'success': False, 'message': 'Workout plan not found'}), 404

        if workout_plan.user_id != current_user.id:
            logger.error(f"Unauthorized access: user={current_user.id}, plan_user={workout_plan.user_id}")
            return jsonify({'success': False, 'message': 'Unauthorized access to workout plan'}), 403

        exercise = Exercise.query.get(exercise_id)
        if not exercise:
            logger.error(f"Exercise not found: exercise_id={exercise_id}")
            return jsonify({'success': False, 'message': 'Exercise not found'}), 404

        # Check for duplicates
        existing = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
        if existing:
            logger.debug(f"Duplicate exercise: plan_id={plan_id}, exercise_id={exercise_id}")
            return jsonify({'success': False, 'message': 'Exercise already in workout plan'}), 400

        # Determine next order
        max_order = db.session.scalars(
            select(WorkoutPlanExercise.order)
            .filter_by(workout_plan_id=plan_id)
            .order_by(WorkoutPlanExercise.order.desc())
        ).first()
        next_order = (max_order + 1) if max_order is not None else 0

        # Add new exercise
        new_entry = WorkoutPlanExercise(
            workout_plan_id=plan_id,
            exercise_id=exercise_id,
            sets=3,
            reps=10,
            weight=0.0,
            order=next_order
        )
        db.session.add(new_entry)
        db.session.commit()

        logger.debug(f"Exercise added: plan_id={plan_id}, exercise_name={exercise.name}")
        return jsonify({'success': True, 'message': f'{exercise.name} added to workout plan'})

    except CSRFError as e:
        logger.error(f"CSRF error: {str(e)}, received={request.headers.get('X-CSRF-Token')}")
        return jsonify({'success': False, 'message': 'Invalid or missing CSRF token'}), 403
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in add_exercise: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500


@main.route('/workout/<int:plan_id>/add_exercise/<int:exercise_id>', methods=['POST'])
@login_required
def add_exercise_to_workout(plan_id, exercise_id):
    logger.debug(f"Add exercise to plan, user: {current_user.name}, plan_id: {plan_id}, exercise_id: {exercise_id}")
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    exercise = Exercise.query.get_or_404(exercise_id)

    existing = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Exercise already in workout plan'}), 400

    max_order = db.session.scalars(
        select(WorkoutPlanExercise.order)
        .filter_by(workout_plan_id=plan_id)
        .order_by(WorkoutPlanExercise.order.desc())
    ).first()
    next_order = (max_order + 1) if max_order is not None else 0

    new_entry = WorkoutPlanExercise(
        workout_plan_id=plan_id,
        exercise_id=exercise_id,
        sets=3,
        reps=10,
        weight=0.0,
        order=next_order
    )
    db.session.add(new_entry)
    db.session.commit()

    flash(f"{exercise.name} toegevoegd aan workout!", "success")
    return jsonify({'success': True, 'message': 'Exercise added to workout plan'})


@main.route('/workout/<int:workout_id>/delete', methods=['POST'])
@login_required
def delete_workout(workout_id):
    workout = WorkoutPlan.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        flash("Je mag alleen je eigen workouts verwijderen.", "danger")
        return redirect(url_for('main.index'))

    # Verwijder expliciet de relaties (associatie-objecten)
    WorkoutPlanExercise.query.filter_by(workout_plan_id=workout.id).delete()

    db.session.delete(workout)
    db.session.commit()

    flash("Workout succesvol verwijderd.", "success")
    return redirect(url_for('main.index'))

@main.route('/add_set', methods=['POST'])
@login_required
def add_set():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    plan_id = data.get('plan_id')

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    plan_exercise = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
    if plan_exercise:
        plan_exercise.sets += 1
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Exercise not found'}), 404


@main.route('/complete_all_sets', methods=['POST'])
@login_required
def complete_all_sets():
    data = request.get_json()
    exercise_id = data.get('exercise_id')
    plan_id = data.get('plan_id')

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    plan_exercise = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
    if plan_exercise:
        exercise_log = ExerciseLog(
            user_id=current_user.id,
            exercise_id=exercise_id,
            workout_plan_id=plan_id,
            sets=plan_exercise.sets,
            reps=plan_exercise.reps,
            weight=plan_exercise.weight,
            completed=True,
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add(exercise_log)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Exercise not found'}), 404


@main.route('/update_exercise_order', methods=['POST'])
@login_required
def update_exercise_order():
    data = request.get_json()
    plan_id = data.get('plan_id')
    order = data.get('order')

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    for index, exercise_id in enumerate(order):
        plan_exercise = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
        if plan_exercise:
            plan_exercise.order = index
    db.session.commit()
    return jsonify({'success': True})


@main.route('/search_exercise', methods=['GET'])
@login_required
def search_exercise():
    form = SearchExerciseForm(request.args)

    # Haal plan_id uit querystring of sessie
    plan_id = request.args.get('plan_id', session.get('current_workout_plan_id'), type=int)

    # Haal plan op of maak nieuw plan aan
    plan = WorkoutPlan.query.get(plan_id)
    if not plan:
        plan = WorkoutPlan(user_id=current_user.id, name="Nieuw Plan")
        db.session.add(plan)
        db.session.commit()

    # Update sessie en plan_id
    session['current_workout_plan_id'] = plan.id
    plan_id = plan.id

    # Oefeningen-query
    query = Exercise.query

    if form.validate():
        if form.search_term.data:
            query = query.filter(Exercise.name.ilike(f"%{form.search_term.data}%"))
        if form.difficulty.data:
            query = query.filter_by(difficulty=form.difficulty.data)
        if form.mechanic.data:
            query = query.filter_by(mechanic=form.mechanic.data)
        if form.exercise_type.data:
            query = query.filter_by(exercise_type=form.exercise_type.data)
        if form.category.data:
            query = query.filter_by(category=form.category.data)

    # Pagination
    page = request.args.get('page', 1, type=int)
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    exercises = pagination.items

    # Fix image paths
    for exercise in exercises:
        if exercise.images and exercise.images.startswith('['):
            try:
                images_list = json.loads(exercise.images)
                exercise.image_url = fix_image_path(images_list[0])
            except Exception:
                exercise.image_url = fix_image_path(exercise.images)
        else:
            exercise.image_url = fix_image_path(exercise.images) if exercise.images else 'default.jpg'

    # AJAX-verzoek? -> alleen oefeningen (HTML-fragment)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('_exercise_items.html', exercises=exercises)

    # Gewoon GET-verzoek -> volledige pagina renderen
    return render_template(
        'search_exercise.html',
        form=form,
        exercises=exercises,
        plan_id=plan.id,
        pagination=pagination
    )


@main.route('/exercise/<int:exercise_id>')
@login_required
def exercise_detail(exercise_id):
    exercise = Exercise.query.get_or_404(exercise_id)

    # Zet de images correct om naar lijst als het een string is
    raw_images = exercise.images or []
    if isinstance(raw_images, str):
        try:
            raw_images = json.loads(raw_images)
        except Exception as e:
            logger.error(f"Kon images niet parsen: {raw_images} — fout: {e}")
            raw_images = []

    fixed_images = [fix_image_path(img) for img in raw_images]

    raw_instructions = exercise.instructions or []
    if isinstance(raw_instructions, str):
        try:
            raw_instructions = json.loads(raw_instructions)
        except Exception as e:
            logger.error(f"Kon instructies niet parsen: {raw_instructions} — fout: {e}")
            raw_instructions = []

    cleaned_instructions = [clean_instruction_text(step) for step in raw_instructions]

    exercise_dict = {
        'name': exercise.name,
        'images': fixed_images,
        'instructions': cleaned_instructions,
        'level': exercise.level,
        'equipment': exercise.equipment,
        'mechanic': exercise.mechanic,
        'category': exercise.category,
    }

    logger.debug(f"Images in exercise_dict: {exercise_dict['images']}")
    return render_template('exercise_detail.html', exercise=exercise_dict)

@main.route('/plan/<int:plan_id>/exercise/<int:exercise_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exercise(plan_id, exercise_id):
    data = request.get_json()

    sets = data.get('sets')
    reps = data.get('reps')
    weight = data.get('weight')

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    plan_exercise = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id, exercise_id=exercise_id).first()
    if not plan_exercise:
        return jsonify({'success': False, 'error': 'Exercise not found in workout plan'}), 404

    try:
        # Update the fields if provided
        if sets is not None:
            plan_exercise.sets = int(sets)
        if reps is not None:
            plan_exercise.reps = int(reps)
        if weight is not None:
            plan_exercise.weight = float(weight)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@main.route('/remove_workout/<int:plan_id>', methods=['POST'])
@login_required
def remove_workout(plan_id):
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)

    if workout_plan.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout.", "error")
        return redirect(url_for('main.index'))

    try:
        WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).delete()
        db.session.delete(workout_plan)
        db.session.commit()
        flash('Workout succesvol verwijderd.', 'success')
        return redirect(url_for('main.index'))

    except Exception as e:
        db.session.rollback()
        flash('Er is iets fout gegaan bij het verwijderen van de workout.', 'error')
        return redirect(url_for('main.edit_workout', plan_id=plan_id))