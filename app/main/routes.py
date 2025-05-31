from flask import render_template, request, current_app, session, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user, login_user, logout_user
from app.forms import EditProfileForm, NameForm, SearchExerciseForm, CurrentWeightForm, WorkoutPlanForm, \
    ExerciseLogForm, GoalWeightForm, ExerciseForm,ActiveWorkoutForm, SimpleWorkoutPlanForm, DeleteWorkoutForm, DeleteExerciseForm
from app.models import Exercise, WorkoutPlanExercise, WorkoutPlan, ExerciseLog, SetLog, WorkoutSession
import logging
from flask_wtf.csrf import generate_csrf,  validate_csrf, CSRFError
from datetime import datetime, timezone
from sqlalchemy import select
import uuid


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

    # Only fetch non-archived workout plans
    workout_plans = WorkoutPlan.query.filter_by(user_id=current_user.id, is_archived=False).all()

    workout_data = []
    for plan in workout_plans:
        exercises = plan.exercises.order_by(WorkoutPlanExercise.order).all()  # lijst van WorkoutPlanExercise objecten
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

        # Delete the WorkoutPlanExercise record
        logger.debug(f"Deleting exercise {wpe_id} with exercise_id {wpe.exercise_id} from plan {plan_id}")
        db.session.delete(wpe)

        # Reorder remaining exercises
        with db.session.no_autoflush:
            remaining_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(
                WorkoutPlanExercise.order).all()
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

    # Maak een nieuwe workout sessie aan
    session_id = str(uuid.uuid4())
    workout_session = WorkoutSession(
        id=session_id,
        user_id=current_user.id,
        workout_plan_id=plan_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(workout_session)
    try:
        db.session.commit()
        logger.debug(f"Created workout_session: id={session_id}, started_at={workout_session.started_at}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create workout session: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to start workout'}), 500


    # Sla session_id op in browser session voor tracking
    session['current_workout_session'] = session_id

    exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()
    form = ActiveWorkoutForm()
    return render_template('active_workout.html',
                           workout_plan=workout_plan,
                           exercises=exercises,
                           session_id=session_id,
                           form=form)

@main.route('/save_workout/<int:plan_id>', methods=['POST'])
@login_required
def save_workout(plan_id):
    logger.debug(f"Saving workout for plan_id={plan_id}, user_id={current_user.id}, session_id={session.get('current_workout_session')}")
    form = ActiveWorkoutForm()
    if not form.validate_on_submit():
        errors = form.errors
        logger.error(f"Form validation failed: {errors}")
        return jsonify({'success': False, 'message': f'Ongeldige formuliergegevens: {errors}'}), 400
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    if workout_plan.user_id != current_user.id:
        logger.error(f"Unauthorized access to plan_id={plan_id}")
        return jsonify({'success': False, 'message': 'Je hebt geen toegang tot deze workout.'}), 403
    wpes = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).all()
    session_id = session.get('current_workout_session')
    if not session_id:
        logger.error("No active workout session found")
        return jsonify({'success': False, 'message': 'Geen actieve workout sessie gevonden.'}), 400
    for wpe in wpes:
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
                    log = SetLog(
                        user_id=current_user.id,
                        workout_plan_id=plan_id,
                        exercise_id=wpe.exercise_id,
                        workout_plan_exercise_id=wpe.id,
                        workout_session_id=session_id,
                        set_number=set_num + 1,
                        reps=reps,
                        weight=weight,
                        completed=True,
                        completed_at=datetime.now(timezone.utc)
                    )
                    db.session.add(log)
                    logger.debug(f"Added SetLog: wpe_id={wpe.id}, set_num={set_num+1}, reps={reps}, weight={weight}")
            set_num += 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {str(e)}")
        return jsonify({'success': False, 'message': f'Database fout: {str(e)}'}), 500
    workout_session = WorkoutSession.query.get(session_id)
    if workout_session:
        workout_session.calculate_statistics()
        try:
            db.session.commit()
            logger.debug(f"Updated statistics for session_id={session_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Statistics update error: {str(e)}")
            return jsonify({'success': False, 'message': f'Statistics update fout: {str(e)}'}), 500
    logger.info("Workout succesvol opgeslagen!")
    return jsonify({'success': True, 'message': 'Workout succesvol opgeslagen!'})



@main.route('/save_set', methods=['POST'])
@login_required
def save_set():
    """Sla een individuele set op tijdens een actieve workout"""
    data = request.get_json()

    wpe_id = data.get('wpe_id')
    set_number = data.get('set_number')
    reps = data.get('reps')
    weight = data.get('weight', 0.0)
    completed = data.get('completed', False)

    if not all([wpe_id, set_number is not None, reps]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400

    try:
        # Haal WorkoutPlanExercise op
        wpe = WorkoutPlanExercise.query.get_or_404(wpe_id)

        # Controleer autorisatie
        if wpe.workout_plan.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Haal huidige workout session op
        session_id = session.get('current_workout_session')
        if not session_id:
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        # Check of deze set al bestaat
        existing_set = SetLog.query.filter_by(
            workout_plan_exercise_id=wpe_id,
            set_number=set_number,
            workout_session_id=session_id
        ).first()

        if existing_set:
            # Update bestaande set
            existing_set.reps = reps
            existing_set.weight = weight
            existing_set.completed = completed
            if completed:
                existing_set.completed_at = datetime.now(timezone.utc)
            set_log = existing_set
        else:
            # Maak nieuwe set aan
            set_log = SetLog(
                user_id=current_user.id,
                workout_plan_id=wpe.workout_plan_id,
                exercise_id=wpe.exercise_id,
                workout_plan_exercise_id=wpe_id,
                set_number=set_number,
                reps=reps,
                weight=weight,
                completed=completed,
                workout_session_id=session_id,
                completed_at=datetime.now(timezone.utc) if completed else None
            )
            db.session.add(set_log)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Set saved successfully',
            'set_id': set_log.id
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving set: {str(e)}")
        return jsonify({'success': False, 'message': f'Error saving set: {str(e)}'}), 500

@main.route('/complete_workout/<int:plan_id>', methods=['POST'])
@login_required
def complete_workout(plan_id):
    logger.debug(f"Attempting to complete workout for plan_id={plan_id}, user_id={current_user.id}")
    try:
        session_id = session.get('current_workout_session')
        logger.debug(f"Session ID: {session_id}")
        if not session_id:
            logger.error("No active workout session found")
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        workout_session = WorkoutSession.query.get_or_404(session_id)
        logger.debug(f"Found workout_session: id={workout_session.id}, user_id={workout_session.user_id}")
        if workout_session.user_id != current_user.id:
            logger.error(f"Unauthorized: session_user_id={workout_session.user_id}, current_user_id={current_user.id}")
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        workout_session.completed_at = datetime.now(timezone.utc)
        workout_session.is_completed = True
        workout_session.calculate_statistics()

        completed_sets = SetLog.query.filter_by(
            workout_session_id=session_id,
            completed=True
        ).all()
        logger.debug(f"Found {len(completed_sets)} completed sets for session_id={session_id}")

        exercise_groups = {}
        for set_log in completed_sets:
            exercise_id = set_log.exercise_id
            if exercise_id not in exercise_groups:
                exercise_groups[exercise_id] = []
            exercise_groups[exercise_id].append(set_log)

        for exercise_id, sets in exercise_groups.items():
            if sets:
                avg_reps = sum(s.reps for s in sets) / len(sets)
                avg_weight = sum(s.weight for s in sets) / len(sets)
                exercise_log = ExerciseLog(
                    user_id=current_user.id,
                    exercise_id=exercise_id,
                    workout_plan_id=plan_id,
                    sets=len(sets),
                    reps=avg_reps,
                    weight=avg_weight,
                    completed=True,
                    completed_at=datetime.now(timezone.utc)
                )
                db.session.add(exercise_log)
                logger.debug(f"Created ExerciseLog: exercise_id={exercise_id}, sets={len(sets)}")

        db.session.commit()
        session.pop('current_workout_session', None)
        logger.info(f"Completed workout_session: id={workout_session.id}, plan_id={plan_id}")
        flash("Workout succesvol voltooid!", "success")
        return jsonify({
            'success': True,
            'message': 'Workout completed successfully',
            'session_stats': workout_session.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Error completing workout: {str(e)}'}), 500


@main.route('/workout_history')
@login_required
def workout_history():
    page = request.args.get('page', 1, type=int)

    sessions = WorkoutSession.query.filter_by(
        user_id=current_user.id,
        is_completed=True,
        is_archived=False  # Alleen niet-gearchiveerde sessies
    ).options(
        db.joinedload(WorkoutSession.workout_plan)
    ).order_by(WorkoutSession.completed_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    for session in sessions.items:
        if not hasattr(session, '_stats_calculated'):
            completed_sets = SetLog.query.filter_by(
                workout_session_id=session.id,
                completed=True
            ).all()

            session.total_sets_count = len(completed_sets)
            session.total_reps_count = sum(s.reps for s in completed_sets)
            session.total_weight_count = sum(s.weight * s.reps for s in completed_sets)

            if session.completed_at and session.started_at:
                duration = session.completed_at - session.started_at
                session.duration_minutes = round(duration.total_seconds() / 60)
            else:
                session.duration_minutes = 0

            session._stats_calculated = True

    return render_template('workout_history.html', sessions=sessions)


@main.route('/workout_session/<session_id>')
@login_required
def workout_session_detail(session_id):
    workout_session = WorkoutSession.query.get_or_404(session_id)

    if workout_session.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout sessie.", "error")
        return redirect(url_for('main.workout_history'))

    # Haal alle voltooide sets op voor deze sessie
    set_logs = SetLog.query.filter_by(
        workout_session_id=session_id,
        completed=True
    ).options(
        db.joinedload(SetLog.exercise)
    ).order_by(SetLog.exercise_id, SetLog.set_number).all()

    # Groepeer per oefening en bereken statistieken
    exercise_groups = {}
    total_sets = 0
    total_reps = 0
    total_weight = 0

    for set_log in set_logs:
        exercise_id = set_log.exercise_id
        if exercise_id not in exercise_groups:
            exercise_groups[exercise_id] = {
                'exercise': set_log.exercise,
                'sets': [],
                'total_reps': 0,
                'total_weight': 0,
                'max_weight': 0
            }

        exercise_groups[exercise_id]['sets'].append(set_log)
        exercise_groups[exercise_id]['total_reps'] += set_log.reps
        exercise_groups[exercise_id]['total_weight'] += (set_log.weight * set_log.reps)

        if set_log.weight > exercise_groups[exercise_id]['max_weight']:
            exercise_groups[exercise_id]['max_weight'] = set_log.weight

        total_sets += 1
        total_reps += set_log.reps
        total_weight += (set_log.weight * set_log.reps)

    # Bereken workout duur
    if workout_session.completed_at and workout_session.started_at:
        duration = workout_session.completed_at - workout_session.started_at
        duration_minutes = round(duration.total_seconds() / 60)
    else:
        duration_minutes = 0

    # Update workout session statistieken als ze nog niet bestaan
    if not workout_session.total_sets:
        workout_session.total_sets = total_sets
        workout_session.total_reps = total_reps
        workout_session.total_weight = total_weight
        workout_session.duration_minutes = duration_minutes
        db.session.commit()

    return render_template('workout_session_detail.html',
                           workout_session=workout_session,
                           exercise_groups=exercise_groups,
                           total_sets=total_sets,
                           total_reps=total_reps,
                           total_weight=total_weight,
                           duration_minutes=duration_minutes)


@main.route('/debug/workout_data')
@login_required
def debug_workout_data():
    """Debug route om te zien wat er in de database staat"""
    if not current_app.debug:  # Alleen in debug mode
        abort(404)

    # Check WorkoutSessions
    sessions = WorkoutSession.query.filter_by(user_id=current_user.id).all()

    debug_data = {
        'user_id': current_user.id,
        'total_sessions': len(sessions),
        'sessions': []
    }

    for session in sessions:
        # Count sets for this session
        set_count = SetLog.query.filter_by(workout_session_id=session.id).count()
        completed_set_count = SetLog.query.filter_by(workout_session_id=session.id, completed=True).count()

        session_data = {
            'id': session.id,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'is_completed': session.is_completed,
            'workout_plan_name': session.workout_plan.name if session.workout_plan else 'No plan',
            'total_sets_in_db': set_count,
            'completed_sets_in_db': completed_set_count,
            'session_attributes': {
                'total_sets': getattr(session, 'total_sets', 'Not set'),
                'total_reps': getattr(session, 'total_reps', 'Not set'),
                'total_weight': getattr(session, 'total_weight', 'Not set'),
                'duration_minutes': getattr(session, 'duration_minutes', 'Not set')
            }
        }
        debug_data['sessions'].append(session_data)

    # Check SetLogs
    all_sets = SetLog.query.filter_by(user_id=current_user.id).all()
    debug_data['total_set_logs'] = len(all_sets)
    debug_data['completed_set_logs'] = len([s for s in all_sets if s.completed])

    # Check ExerciseLogs (oude manier)
    exercise_logs = ExerciseLog.query.filter_by(user_id=current_user.id).all()
    debug_data['total_exercise_logs'] = len(exercise_logs)

    return jsonify(debug_data)


# Ook een debug route voor een specifieke sessie:
@main.route('/debug/session/<session_id>')
@login_required
def debug_session_data(session_id):
    """Debug route voor een specifieke sessie"""
    if not current_app.debug:
        abort(404)

    session = WorkoutSession.query.get_or_404(session_id)
    if session.user_id != current_user.id:
        abort(403)

    sets = SetLog.query.filter_by(workout_session_id=session_id).all()

    debug_data = {
        'session_id': session_id,
        'session_data': {
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'is_completed': session.is_completed,
            'workout_plan': session.workout_plan.name if session.workout_plan else None
        },
        'sets': []
    }

    for set_log in sets:
        set_data = {
            'id': set_log.id,
            'exercise_name': set_log.exercise.name if set_log.exercise else 'Unknown',
            'set_number': set_log.set_number,
            'reps': set_log.reps,
            'weight': set_log.weight,
            'completed': set_log.completed,
            'completed_at': set_log.completed_at.isoformat() if set_log.completed_at else None
        }
        debug_data['sets'].append(set_data)

    return jsonify(debug_data)


@main.route('/get_workout_progress/<session_id>')
@login_required
def get_workout_progress(session_id):
    workout_session = WorkoutSession.query.get_or_404(session_id)

    if workout_session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    completed_sets = SetLog.query.filter_by(
        workout_session_id=session_id,
        completed=True
    ).count()

    total_planned_sets = db.session.query(db.func.sum(WorkoutPlanExercise.sets)).filter_by(
        workout_plan_id=workout_session.workout_plan_id
    ).scalar() or 0

    progress_percentage = (completed_sets / total_planned_sets * 100) if total_planned_sets > 0 else 0

    return jsonify({
        'completed_sets': completed_sets,
        'total_planned_sets': total_planned_sets,
        'progress_percentage': round(progress_percentage, 1),
        'session_duration': (datetime.now(timezone.utc) - workout_session.started_at).total_seconds() / 60
    })


@main.route('/archive_workout_session/<session_id>', methods=['POST'])
@login_required
def archive_workout_session(session_id):
    logger.debug(f"Archiving workout session: session_id={session_id}, user_id={current_user.id}")

    workout_session = WorkoutSession.query.get_or_404(session_id)
    if workout_session.user_id != current_user.id:
        logger.error(
            f"Unauthorized access: session_user_id={workout_session.user_id}, current_user_id={current_user.id}")
        flash("Je hebt geen toegang tot deze workout sessie.", "error")
        return redirect(url_for('main.workout_history'))

    workout_session.is_archived = True
    try:
        db.session.commit()
        flash("Workout succesvol gearchiveerd.", "success")
        logger.info(f"Workout session archived: session_id={session_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving workout session: {str(e)}")
        flash("Fout bij het archiveren van de workout.", "error")

    return redirect(url_for('main.workout_history'))

@main.route('/archive_workout/<int:workout_id>', methods=['POST'])
@login_required
def archive_workout(workout_id):
    logger.debug(f"Archiving workout: workout_id={workout_id}, user_id={current_user.id}")
    workout = WorkoutPlan.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        logger.error(f"Unauthorized access: user_id={current_user.id}, workout_user_id={workout.user_id}")
        return jsonify({'success': False, 'message': 'Je hebt geen toegang tot deze workout.'}), 403

    workout.is_archived = True
    try:
        db.session.commit()
        logger.info(f"Workout archived: workout_id={workout_id}")
        return jsonify({'success': True, 'message': 'Workout succesvol gearchiveerd.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Fout bij het archiveren: {str(e)}'}), 500

@main.route('/archived_plans')
@login_required
def archived_plans():
    logger.debug(f"Archived plans route aangeroepen voor {current_user.name}")
    workout_plans = WorkoutPlan.query.filter_by(user_id=current_user.id, is_archived=True).all()

    workout_data = []
    for plan in workout_plans:
        exercises = plan.exercises.order_by(WorkoutPlanExercise.order).all()
        exercise_objs = [entry.exercise for entry in exercises]
        workout_data.append({
            'plan': plan,
            'exercises': exercise_objs
        })

    return render_template('archived_workouts.html', workout_data=workout_data)

@main.route('/unarchive_workout/<int:workout_id>', methods=['POST'])
@login_required
def unarchive_workout(workout_id):
    logger.debug(f"Unarchiving workout: workout_id={workout_id}, user_id={current_user.id}")
    workout = WorkoutPlan.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        logger.error(f"Unauthorized access: user_id={current_user.id}, workout_user_id={workout.user_id}")
        return jsonify({'success': False, 'message': 'Je hebt geen toegang tot deze workout.'}), 403

    workout.is_archived = False
    try:
        db.session.commit()
        logger.info(f"Workout unarchived: workout_id={workout_id}")
        return jsonify({'success': True, 'message': 'Workout succesvol hersteld.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error unarchiving workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Fout bij het herstellen: {str(e)}'}), 500