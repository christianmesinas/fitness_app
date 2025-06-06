import json
from enum import Enum

import pytz
import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime, timezone
from typing import Optional
from app import db
from sqlalchemy.types import TypeDecorator, TEXT
import uuid


class JSONEncodedList(TypeDecorator):
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is None:
            return '[]'
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return json.loads(value)

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
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    current_weight: so.Mapped[Optional[float]] = so.mapped_column()
    fitness_goal: so.Mapped[Optional[float]] = so.mapped_column()
    weekly_workouts: so.Mapped[Optional[int]] = so.mapped_column()
    registration_step: so.Mapped[Optional[str]] = so.mapped_column(sa.String(20), default='name')
    weight_logs: so.WriteOnlyMapped['WeightLog'] = so.relationship(back_populates='user', cascade="all, delete-orphan")

    exercise_logs: so.WriteOnlyMapped['ExerciseLog'] = so.relationship(back_populates='user', cascade="all, delete-orphan")

    # Verwijzing naar alle plannen van deze gebruiker
    workout_plans: so.WriteOnlyMapped['WorkoutPlan'] = so.relationship(
        back_populates='user',
        cascade="all, delete-orphan",
        foreign_keys='WorkoutPlan.user_id'
    )

    # Actieve workout plan
    current_workout_plan_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('workout_plan.id'))
    current_workout_plan: so.Mapped[Optional['WorkoutPlan']] = so.relationship(
        'WorkoutPlan',
        foreign_keys=[current_workout_plan_id],
        post_update=True
    )

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


class WeightLog(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), nullable=False)
    weight: so.Mapped[float] = so.mapped_column(nullable=False)
    logged_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    notes: so.Mapped[Optional[str]] = so.mapped_column(sa.String(200))

    user: so.Mapped['User'] = so.relationship('User', back_populates='weight_logs')

    def __repr__(self):
        return f'<WeightLog {self.weight}kg on {self.logged_at.date()}>'


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

    @property
    def images_list(self):
        try:
            return json.loads(self.images) if self.images else []
        except json.JSONDecodeError:
            return []

    @images_list.setter
    def images_list(self, value):
        self.images = json.dumps(value)

    def to_dict(self):
        image_list = self.images_list  # gebruikt je property, clean en DRY

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
    is_archived: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    created_at: so.Mapped[datetime] = so.mapped_column(default=lambda: datetime.now(timezone.utc))
    user: so.Mapped['User'] = so.relationship(
        back_populates='workout_plans',
        foreign_keys=[user_id]
    )
    exercises = db.relationship("WorkoutPlanExercise", back_populates="workout_plan", lazy="dynamic")

    def __repr__(self):
        return f'<WorkoutPlan {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id,
            'is_archived': self.is_archived
        }

class WorkoutPlanExercise(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    workout_plan_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('workout_plan.id'), index=True)
    exercise_id: so.Mapped[str] = so.mapped_column(sa.ForeignKey('exercise.id'), index=True)
    sets: so.Mapped[Optional[int]] = so.mapped_column()
    reps: so.Mapped[Optional[int]] = so.mapped_column()
    duration: so.Mapped[Optional[int]] = so.mapped_column()
    order: so.Mapped[int] = so.mapped_column(default=0)
    weight: so.Mapped[Optional[float]] = so.mapped_column()

    workout_plan = so.relationship("WorkoutPlan", back_populates="exercises")
    exercise: so.Mapped['Exercise'] = so.relationship()
    set_logs: so.WriteOnlyMapped['SetLog'] = so.relationship(back_populates="workout_plan_exercise")

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

class SetLog(db.Model):
    __tablename__ = 'set_logs'

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    workout_plan_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('workout_plan.id', ondelete='SET NULL'), nullable=True)  # Changed to nullable=True and SET NULL
    exercise_id: so.Mapped[str] = so.mapped_column(sa.ForeignKey('exercise.id', ondelete='CASCADE'), nullable=False)
    workout_plan_exercise_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('workout_plan_exercise.id', ondelete='SET NULL'), nullable=True)
    set_number: so.Mapped[int] = so.mapped_column(nullable=False)
    reps: so.Mapped[int] = so.mapped_column(nullable=False)
    weight: so.Mapped[float] = so.mapped_column(default=0.0)
    completed: so.Mapped[bool] = so.mapped_column(default=False)

    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)

    workout_session_id: so.Mapped[Optional[str]] = so.mapped_column(sa.String(36), nullable=True)

    user: so.Mapped['User'] = so.relationship(backref='set_logs')
    workout_plan: so.Mapped[Optional['WorkoutPlan']] = so.relationship(backref='set_logs')  # Updated to Optional
    exercise: so.Mapped['Exercise'] = so.relationship(backref='set_logs')
    workout_plan_exercise: so.Mapped[Optional['WorkoutPlanExercise']] = so.relationship(back_populates='set_logs')

    def __repr__(self):
        return f'<SetLog {self.id}: User {self.user_id}, Exercise {self.exercise_id}, Set {self.set_number}>'

    def to_dict(self):
        return {
            'id': self.id,
            'set_number': self.set_number,
            'reps': self.reps,
            'weight': self.weight,
            'completed': self.completed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'exercise_name': self.exercise.name if self.exercise else None
        }


class WorkoutSession(db.Model):
    __tablename__ = 'workout_sessions'

    id: so.Mapped[str] = so.mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('user.id'), nullable=False)
    workout_plan_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('workout_plan.id'), nullable=False)

    started_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    duration_minutes: so.Mapped[Optional[int]] = so.mapped_column(nullable=True)

    total_sets: so.Mapped[int] = so.mapped_column(default=0)
    total_reps: so.Mapped[int] = so.mapped_column(default=0)
    total_weight: so.Mapped[float] = so.mapped_column(default=0.0)

    is_completed: so.Mapped[bool] = so.mapped_column(default=False)
    is_archived: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)

    user: so.Mapped['User'] = so.relationship(backref='workout_sessions')
    workout_plan: so.Mapped['WorkoutPlan'] = so.relationship(backref='workout_sessions')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.started_at and self.started_at.tzinfo is None:
            self.started_at = self.started_at.replace(tzinfo=pytz.UTC)
        if self.completed_at and self.completed_at.tzinfo is None:
            self.completed_at = self.completed_at.replace(tzinfo=pytz.UTC)

    def calculate_statistics(self):
        set_logs = SetLog.query.filter_by(workout_session_id=self.id, completed=True).all()

        self.total_sets = len(set_logs)
        self.total_reps = sum(log.reps for log in set_logs)
        self.total_weight = sum(log.reps * log.weight for log in set_logs)

        if self.started_at and self.completed_at:
            started_at = self.started_at if self.started_at.tzinfo else self.started_at.replace(tzinfo=pytz.UTC)
            completed_at = self.completed_at if self.completed_at.tzinfo else self.completed_at.replace(tzinfo=pytz.UTC)
            delta = completed_at - started_at
            self.duration_minutes = int(delta.total_seconds() / 60)
        else:
            self.duration_minutes = 0

    def to_dict(self):
        return {
            'id': self.id,
            'workout_plan_name': self.workout_plan.name if self.workout_plan else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_minutes': self.duration_minutes,
            'total_sets': self.total_sets,
            'total_reps': self.total_reps,
            'total_weight': self.total_weight,
            'is_completed': self.is_completed
        }