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

    if workout_plan.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout.", "error")
        logger.debug(f"User {current_user.id} attempted to access plan_id {plan_id}")
        return redirect(url_for('main.index'))

    form = WorkoutPlanForm()
    logger.debug(f"Initial form.name.data: {form.name.data}, workout_plan.name: {workout_plan.name}")

    plan_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(
        WorkoutPlanExercise.order).all()
    logger.debug(f"Plan exercises: {[pe.id for pe in plan_exercises]}")

    delete_exercise_form = DeleteExerciseForm()

    if request.method == 'GET':
        form.name.data = workout_plan.name
        while form.exercises.entries:
            form.exercises.pop_entry()
        for plan_exercise in plan_exercises:
            exercise_form = ExerciseForm()
            logger.debug(f"Populating exercise_form with exercise_id: {plan_exercise.exercise_id}")
            exercise_form.exercise_id.data = plan_exercise.exercise_id
            exercise_form.sets.data = plan_exercise.sets
            exercise_form.reps.data = plan_exercise.reps
            exercise_form.weight.data = plan_exercise.weight
            exercise_form.order.data = plan_exercise.order or 0
            exercise_form.is_edit.data = 1
            form.exercises.append_entry(exercise_form)
        logger.debug(f"Populated {len(form.exercises.entries)} exercises in form")

    exercises = Exercise.query.all()
    exercises_dict = {str(ex.id): ex for ex in exercises}
    for ex in exercises:
        try:
            ex.images_list = json.loads(ex.images) if ex.images else []
            logger.debug(f"Exercise {ex.id}: images_list = {ex.images_list}")
        except Exception:
            ex.images_list = []
            logger.error(f"Failed to parse images for exercise {ex.id}")

    if request.method == 'POST':
        logger.debug(f"POST data: {request.form}")
        if form.validate_on_submit():
            # Update workout name
            workout_plan.name = form.name.data
            db.session.add(workout_plan)

            # Update existing exercises instead of deleting
            for idx, exercise_form in enumerate(form.exercises):
                exercise_id = exercise_form.exercise_id.data
                if exercise_id == 0:
                    logger.debug(f"Skipping exercise {idx} with exercise_id=0")
                    continue
                logger.debug(f"Processing exercise with exercise_id: {exercise_id}, order: {exercise_form.order.data}")
                # Find matching WorkoutPlanExercise by workout_plan_id, exercise_id, and order
                plan_exercise = WorkoutPlanExercise.query.filter_by(
                    workout_plan_id=plan_id,
                    exercise_id=exercise_id,
                    order=exercise_form.order.data
                ).first()
                if plan_exercise:
                    # Update existing exercise
                    plan_exercise.sets = exercise_form.sets.data or 0
                    plan_exercise.reps = exercise_form.reps.data or 0
                    plan_exercise.weight = exercise_form.weight.data or 0.0
                    plan_exercise.order = idx
                    db.session.add(plan_exercise)
                    logger.debug(
                        f"Updated exercise {plan_exercise.id}: sets={plan_exercise.sets}, reps={plan_exercise.reps}, weight={plan_exercise.weight}")
                else:
                    # Create new exercise (if added)
                    logger.debug(f"Creating new exercise with exercise_id: {exercise_id}")
                    plan_exercise = WorkoutPlanExercise(
                        workout_plan_id=workout_plan.id,
                        exercise_id=exercise_id,
                        sets=exercise_form.sets.data or 0,
                        reps=exercise_form.reps.data or 0,
                        weight=exercise_form.weight.data or 0.0,
                        order=idx
                    )
                    db.session.add(plan_exercise)

            try:
                db.session.commit()
                flash('Workout bijgewerkt!', 'success')
                logger.debug(
                    f"Workout updated, new name: {workout_plan.name}, exercises processed: {len(form.exercises)}")
            except Exception as e:
                db.session.rollback()
                flash('Er is iets fout gegaan bij het opslaan.', 'error')
                logger.error(f"Database commit failed: {str(e)}")

            return redirect(url_for('main.edit_workout', plan_id=plan_id))
        else:
            logger.error(f"Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Fout in {field}: {error}", 'error')

    exercise_pairs = [(pe, form.exercises.entries[i]) for i, pe in enumerate(plan_exercises)]
    logger.debug(
        f"exercise_pairs length: {len(exercise_pairs)}, plan_exercises length: {len(plan_exercises)}, form.exercises.entries length: {len(form.exercises.entries)}")

    return render_template(
        'edit_workout.html',
        form=form,
        workout_plan=workout_plan,
        exercises_dict=exercises_dict,
        delete_exercise_form=delete_exercise_form,
        exercise_pairs=exercise_pairs,
        plan_exercises=plan_exercises
    )


@main.route('/delete_exercise_from_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_exercise_from_plan(plan_id):
    logger.debug(f"Delete POST data: {request.form}")

    wpe_id = request.form.get('workout_plan_exercise_id')

    if not wpe_id:
        flash("Ongeldig item ID.", "error")
        logger.error("No workout_plan_exercise_id in POST data")
        return redirect(url_for('main.edit_workout', plan_id=plan_id))

    try:
        wpe_id = int(wpe_id)
    except (ValueError, TypeError):
        flash("Ongeldig item ID.", "error")
        logger.error(f"Invalid workout_plan_exercise_id: {wpe_id}")
        return redirect(url_for('main.edit_workout', plan_id=plan_id))

    form = DeleteExerciseForm()
    if form.validate_on_submit():
        wpe = WorkoutPlanExercise.query.get_or_404(wpe_id)
        logger.debug(f"Found WorkoutPlanExercise: id={wpe.id}, exercise_id={wpe.exercise_id}, order={wpe.order}")
        if wpe.workout_plan_id != plan_id:
            flash("Deze oefening hoort niet bij dit plan.", "error")
            logger.error(f"Exercise {wpe_id} does not belong to plan {plan_id}")
            return redirect(url_for('main.edit_workout', plan_id=plan_id))

        workout_plan = WorkoutPlan.query.get_or_404(plan_id)
        if workout_plan.user_id != current_user.id:
            flash("Geen toegang tot dit plan.", "error")
            logger.error(f"User {current_user.id} not authorized for plan {plan_id}")
            return redirect(url_for('main.index'))

        logger.debug(f"Deleting exercise {wpe_id} with exercise_id {wpe.exercise_id} from plan {plan_id}")
        db.session.delete(wpe)

        remaining_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(
            WorkoutPlanExercise.order).all()
        logger.debug(f"Remaining exercises: {[e.id for e in remaining_exercises]}")
        for idx, exercise in enumerate(remaining_exercises):
            exercise.order = idx
            db.session.add(exercise)

        try:
            db.session.commit()
            flash("Oefening verwijderd.", "success")
            logger.debug(f"Successfully deleted exercise {wpe_id}")
        except Exception as e:
            db.session.rollback()
            flash("Fout bij het verwijderen van de oefening.", "error")
            logger.error(f"Delete failed: {str(e)}")
    else:
        flash("Ongeldig formulier.", "error")
        logger.error(f"DeleteExerciseForm validation failed: {form.errors}")

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


@main.route('/start_workout/<int:plan_id>', methods=['GET'])
@login_required
def start_workout(plan_id):
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout.", "error")
        return redirect(url_for('main.index'))
    exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()
    return render_template('active_workout.html', workout_plan=workout_plan, exercises=exercises)

@main.route('/save_workout/<int:plan_id>', methods=['POST'])
@login_required
def save_workout(plan_id):
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout.", "error")
        return redirect(url_for('main.index'))
    wpes = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).all()
    for wpe in wpes:
        completed_sets = []
        set_num = 0
        while True:
            completed_key = f'completed_{wpe.id}_{set_num}'
            if completed_key not in request.form:
                break
            if request.form[completed_key]:
                reps_key = f'reps_{wpe.id}_{set_num}'
                weight_key = f'weight_{wpe.id}_{set_num}'
                reps = request.form.get(reps_key, type=float)
                weight = request.form.get(weight_key, type=float)
                if reps is not None and weight is not None:
                    completed_sets.append({'reps': reps, 'weight': weight})
            set_num += 1
        if completed_sets:

            total_reps = sum(set['reps'] for set in completed_sets)
            total_weight = sum(set['weight'] for set in completed_sets)
            num_sets = len(completed_sets)
            avg_reps = total_reps / num_sets if num_sets > 0 else 0
            avg_weight = total_weight / num_sets if num_sets > 0 else 0
            log = ExerciseLog(
                user_id=current_user.id,
                exercise_id=wpe.exercise_id,
                workout_plan_id=plan_id,
                sets=num_sets,
                reps=avg_reps,
                weight=avg_weight,
                completed=True,
                completed_at=datetime.now(timezone.utc)
            )
            db.session.add(log)
    db.session.commit()
    flash("Workout saved successfully!", "success")
    return redirect(url_for('main.index'))