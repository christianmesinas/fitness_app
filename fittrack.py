import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, create_app
from dotenv import load_dotenv
from app.models import User, Exercise, ExerciseMuscle, WorkoutPlan, WorkoutPlanExercise, ExerciseLog

load_dotenv()

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'sa': sa,
        'so': so,
        'db': db,
        'User': User,
        'Exercise': Exercise,
        'ExerciseMuscle': ExerciseMuscle,
        'WorkoutPlan': WorkoutPlan,
        'WorkoutPlanExercise': WorkoutPlanExercise,
        'ExerciseLog': ExerciseLog
    }