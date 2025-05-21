import json
from enum import Enum
import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime, timezone
from typing import Optional
from app import db

class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"

class Force(str, Enum):
    STATIC = "static"
    PULL = "pull"
    PUSH = "push"

class Mechanic(str, Enum):
    ISOLATION = "isolation"
    COMPOUND = "compound"

class Equipment(str, Enum):
    MEDICINE_BALL = "medicine ball"
    DUMBBELL = "dumbbell"
    BODY_ONLY = "body only"
    BANDS = "bands"
    KETTLEBELLS = "kettlebells"
    FOAM_ROLL = "foam roll"
    CABLE = "cable"
    MACHINE = "machine"
    BARBELL = "barbell"
    EXERCISE_BALL = "exercise ball"
    E_Z_CURL_BAR = "e-z curl bar"
    OTHER = "other"

class Muscle(str, Enum):
    ABDOMINALS = "abdominals"
    ABDUCTORS = "abductors"
    ADDUCTORS = "adductors"
    BICEPS = "biceps"
    CALVES = "calves"
    CHEST = "chest"
    FOREARMS = "forearms"
    GLUTES = "glutes"
    HAMSTRINGS = "hamstrings"
    LATS = "lats"
    LOWER_BACK = "lower back"
    MIDDLE_BACK = "middle back"
    NECK = "neck"
    QUADRICEPS = "quadriceps"
    SHOULDERS = "shoulders"
    TRAPS = "traps"
    TRICEPS = "triceps"

class Category(str, Enum):
    POWERLIFTING = "powerlifting"
    STRENGTH = "strength"
    STRETCHING = "stretching"
    CARDIO = "cardio"
    OLYMPIC_WEIGHTLIFTING = "olympic weightlifting"
    STRONGMAN = "strongman"
    PLYOMETRICS = "plyometrics"

class User(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    auth0_id: so.Mapped[str] = so.mapped_column(sa.String(64), unique=True, nullable=False)
    name: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), index=True, nullable=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True, nullable=False)
    sub: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128), unique=True, nullable=True)  # Nullable
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    current_weight: so.Mapped[Optional[float]] = so.mapped_column()
    fitness_goal: so.Mapped[Optional[float]] = so.mapped_column()
    weekly_workouts: so.Mapped[Optional[int]] = so.mapped_column()
    registration_step: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20), default='name')

    workout_plans: so.WriteOnlyMapped['WorkoutPlan'] = so.relationship(back_populates='user', cascade="all, delete-orphan")
    exercise_logs: so.WriteOnlyMapped['ExerciseLog'] = so.relationship(back_populates='user', cascade="all, delete-orphan")

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.name,
            'email': self.email,
            'fitness_goal': self.fitness_goal,
            'current_weight': self.current_weight,
            'weekly_workouts': self.weekly_workouts,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None
        }



exercise_muscle_association = sa.Table(
    'exercise_muscle_association',
    db.metadata,
    sa.Column('exercise_id', sa.String(50), sa.ForeignKey('exercise.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('muscle_id', sa.Integer, sa.ForeignKey('exercise_muscle.id', ondelete='CASCADE'), primary_key=True),
    sa.Column('is_primary', sa.Boolean, nullable=False)
)

class ExerciseMuscle(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    muscle: so.Mapped[str] = so.mapped_column(sa.Enum(Muscle), nullable=False)

    exercises_primary: so.WriteOnlyMapped['Exercise'] = so.relationship(
        secondary=lambda: exercise_muscle_association,
        primaryjoin=lambda: (exercise_muscle_association.c.muscle_id == ExerciseMuscle.id) & (exercise_muscle_association.c.is_primary == True),
        back_populates='primary_muscles',
        overlaps="exercises_secondary,secondary_muscles"
    )
    exercises_secondary: so.WriteOnlyMapped['Exercise'] = so.relationship(
        secondary=lambda: exercise_muscle_association,
        primaryjoin=lambda: (exercise_muscle_association.c.muscle_id == ExerciseMuscle.id) & (exercise_muscle_association.c.is_primary == False),
        back_populates='secondary_muscles',
        overlaps="exercises_primary,primary_muscles"
    )

    def __repr__(self):
        return f'<ExerciseMuscle {self.muscle}>'

class Exercise(db.Model):
    id: so.Mapped[str] = so.mapped_column(sa.String(50), primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), index=True)
    force: so.Mapped[Optional[str]] = so.mapped_column(sa.Enum(Force))
    level: so.Mapped[str] = so.mapped_column(sa.Enum(ExperienceLevel), index=True)
    mechanic: so.Mapped[Optional[str]] = so.mapped_column(sa.Enum(Mechanic))
    equipment: so.Mapped[Optional[str]] = so.mapped_column(sa.Enum(Equipment), index=True)
    category: so.Mapped[str] = so.mapped_column(sa.Enum(Category), index=True)
    instructions: so.Mapped[str] = so.mapped_column(sa.Text)
    images: so.Mapped[str] = so.mapped_column(sa.Text)

    primary_muscles: so.WriteOnlyMapped['ExerciseMuscle'] = so.relationship(
        secondary=lambda: exercise_muscle_association,
        primaryjoin=lambda: (exercise_muscle_association.c.exercise_id == Exercise.id) & (exercise_muscle_association.c.is_primary == True),
        back_populates='exercises_primary',
        overlaps = "exercises_secondary,secondary_muscles"
    )
    secondary_muscles: so.WriteOnlyMapped['ExerciseMuscle'] = so.relationship(
        primaryjoin=lambda: (exercise_muscle_association.c.exercise_id == Exercise.id) & (exercise_muscle_association.c.is_primary == False),
        secondary=lambda: exercise_muscle_association,
        back_populates='exercises_secondary',
        overlaps="exercises_primary,primary_muscles"
    )

    def __repr__(self):
        return f'<Exercise {self.name}>'

    def to_dict(self):
        try:
            image_list = json.loads(self.images) if self.images else []
        except json.JSONDecodeError:
            image_list = []

        # Zorg dat het pad het juiste prefix heeft
        fixed_images = []
        for img_path in image_list:
            if not img_path.startswith("img/exercises/"):
                safe_name = self.name.strip().replace(" ", "_")
                fixed_images.append(f"img/exercises/{safe_name}/0.jpg")
            else:
                fixed_images.append(img_path)

        if not fixed_images:
            safe_name = self.name.strip().replace(" ", "_")
            fixed_images = [f"img/exercises/{safe_name}/0.jpg"]

        return {
            'id': self.id,
            'name': self.name,
            'force': self.force,
            'level': self.level,
            'mechanic': self.mechanic,
            'equipment': self.equipment,
            'instructions': json.loads(self.instructions) if self.instructions else [],
            'category': self.category,
            'images': fixed_images
        }


class WorkoutPlan(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), index=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100))
    created_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    start_date: so.Mapped[Optional[datetime]] = so.mapped_column()
    end_date: so.Mapped[Optional[datetime]] = so.mapped_column()
    user: so.Mapped['User'] = so.relationship(back_populates='workout_plans')
    exercises: so.WriteOnlyMapped['WorkoutPlanExercise'] = so.relationship(back_populates='workout_plan')

    def __repr__(self):
        return f'<WorkoutPlan {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'user_id': self.user_id
        }

class WorkoutPlanExercise(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    workout_plan_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('workout_plan.id'), index=True)
    exercise_id: so.Mapped[str] = so.mapped_column(sa.ForeignKey('exercise.id'), index=True)
    day_of_week: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20))
    sets: so.Mapped[Optional[int]] = so.mapped_column()
    reps: so.Mapped[Optional[int]] = so.mapped_column()
    duration: so.Mapped[Optional[int]] = so.mapped_column()
    order: so.Mapped[int] = so.mapped_column(default=0)

    workout_plan: so.Mapped['WorkoutPlan'] = so.relationship(back_populates='exercises')
    exercise: so.Mapped['Exercise'] = so.relationship()

    def __repr__(self):
        return f'<WorkoutPlanExercise {self.exercise_id} in {self.workout_plan_id}>'

class ExerciseLog(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), index=True)
    exercise_id: so.Mapped[str] = so.mapped_column(sa.ForeignKey('exercise.id'), index=True)
    workout_plan_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('workout_plan.id'), index=True)
    completed_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    completed: so.Mapped[bool] = so.mapped_column(default=False)
    sets: so.Mapped[Optional[int]] = so.mapped_column()
    reps: so.Mapped[Optional[int]] = so.mapped_column()
    weight: so.Mapped[Optional[float]] = so.mapped_column()
    duration: so.Mapped[Optional[int]] = so.mapped_column()
    notes: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)

    user: so.Mapped['User'] = so.relationship(back_populates='exercise_logs')
    exercise: so.Mapped['Exercise'] = so.relationship()
    workout_plan: so.Mapped[Optional['WorkoutPlan']] = so.relationship()

    def __repr__(self):
        return f'<ExerciseLog {self.exercise_id} by {self.user_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'exercise_id': self.exercise_id,
            'workout_plan_id': self.workout_plan_id,
            'completed_at': self.completed_at.isoformat(),
            'completed': self.completed,
            'sets': self.sets,
            'reps': self.reps,
            'weight': self.weight,
            'duration': self.duration,
            'notes': self.notes
        }