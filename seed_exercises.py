import json
import csv
import re
from app import db, create_app
from app.models import Exercise, ExerciseMuscle, exercise_muscle_association
from sqlalchemy.exc import IntegrityError
import chardet

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'

def detect_delimiter(file_path, encoding):
    with open(file_path, newline='', encoding=encoding, errors='replace') as csvfile:
        first_line = csvfile.readline().strip()
        delimiters = [',', ';', '\t']
        max_fields = 0
        best_delimiter = ','
        for delimiter in delimiters:
            fields = first_line.split(delimiter)
            if len(fields) > max_fields:
                max_fields = len(fields)
                best_delimiter = delimiter
        return best_delimiter

def clean_muscle_field(muscle_field):
    """Parse JSON-like muscle field and return a list of unique muscle names."""
    if not muscle_field:
        return []
    try:
        muscles = json.loads(muscle_field)
        if isinstance(muscles, str):
            return [muscles.strip()]
        return list(set(m.strip() for m in muscles if m.strip()))  # Deduplicate
    except json.JSONDecodeError:
        return list(set(m.strip() for m in muscle_field.split(',') if m.strip()))  # Deduplicate

def map_muscle_to_enum(muscle):
    """Map muscle name to valid ENUM value."""
    muscle = muscle.lower()
    muscle_mapping = {
        'quadriceps': 'QUADRICEPS',
        'glutes': 'GLUTES',
        'hamstrings': 'HAMSTRINGS',
        'chest': 'CHEST',
        'triceps': 'TRICEPS',
        'shoulders': 'SHOULDERS',
        'biceps': 'BICEPS',
        'abdominals': 'ABDOMINALS',
        'abductors': 'ABDUCTORS',
        'adductors': 'ADDUCTORS',
        'calves': 'CALVES',
        'lower back': 'LOWER_BACK',
        'upper back': 'UPPER_BACK',
        'lats': 'LATS',
        'middle back': 'TRAPS',  # Map 'middle back' to TRAPS
        'traps': 'TRAPS',
        'rhomboids': 'RHOMBOIDS',
        # Add more mappings based on Muscle ENUM
    }
    return muscle_mapping.get(muscle, muscle.upper())

def seed_exercises(csv_file_path):
    app = create_app()
    with app.app_context():
        encoding = detect_encoding(csv_file_path)
        print(f"Detected encoding: {encoding}")

        delimiter = detect_delimiter(csv_file_path, encoding)
        print(f"Using delimiter: '{delimiter}'")

        try:
            with open(csv_file_path, newline='', encoding=encoding, errors='replace') as csvfile:
                reader = csv.DictReader(csvfile, delimiter=delimiter, fieldnames=None)
                # Fix duplicate 'id' by renaming
                fieldnames = reader.fieldnames
                print(f"CSV headers: {fieldnames}")
                if 'id' in fieldnames:
                    fieldnames = ['exercise_id' if f == 'id' and i == 0 else f for i, f in enumerate(fieldnames)]
                    if fieldnames.count('id') > 0:
                        id_indices = [i for i, f in enumerate(fieldnames) if f == 'id']
                        fieldnames[id_indices[-1]] = 'name_id'
                    reader.fieldnames = fieldnames
                    print(f"Adjusted headers: {fieldnames}")

                expected_columns = {'exercise_id', 'name', 'force', 'level', 'mechanic', 'equipment', 'primaryMuscles', 'secondaryMuscles', 'instructions', 'category', 'images', 'name_id'}
                if not expected_columns.issubset(fieldnames):
                    missing = expected_columns - set(fieldnames)
                    print(f"Error: CSV missing columns: {missing}")
                    print("Please ensure the CSV has the correct header or adjust the script's expected_columns.")
                    return

                row_number = 0
                for row in reader:
                    row_number += 1
                    try:
                        if not row['exercise_id'] or not row['name']:
                            print(f"Skipping row {row_number}: Missing exercise_id or name")
                            continue

                        # Debug problematic rows
                        if row_number in [837, 859, 860]:
                            print(f"Debug row {row_number}: name={row['name']}, exercise_id={row['exercise_id']}, name_id={row.get('name_id', '')}, primaryMuscles={clean_muscle_field(row.get('primaryMuscles', ''))}, secondaryMuscles={clean_muscle_field(row.get('secondaryMuscles', ''))}")

                        instructions = row.get('instructions', '')
                        try:
                            instructions_json = json.loads(instructions) if instructions else []
                            if not isinstance(instructions_json, list):
                                instructions_json = [instructions_json]
                            instructions_json = json.dumps(instructions_json)
                        except json.JSONDecodeError:
                            instructions_json = json.dumps([instructions.strip()]) if instructions else '[]'

                        images = row.get('images', '')
                        try:
                            images_json = json.loads(images) if images else []
                            if not isinstance(images_json, list):
                                images_json = [images_json]
                            images_json = json.dumps(images_json)
                        except json.JSONDecodeError:
                            images_json = json.dumps([img.strip() for img in images.split(',') if img.strip()]) if images else '[]'

                        exercise = Exercise(
                            id=row['exercise_id'],
                            name=row['name'],
                            force=row.get('force') or None,
                            level=row.get('level', 'beginner'),
                            mechanic=row.get('mechanic') or None,
                            equipment=row.get('equipment') or None,
                            category=row.get('category', 'strength'),
                            instructions=instructions_json,
                            images=images_json
                        )
                        db.session.add(exercise)
                        db.session.flush()  # Ensure exercise.id is available

                        # Track inserted associations to avoid duplicates
                        inserted_associations = set()

                        primary_muscles = clean_muscle_field(row.get('primaryMuscles', ''))
                        for muscle_name in primary_muscles:
                            if muscle_name:
                                muscle_name = map_muscle_to_enum(muscle_name)
                                muscle = ExerciseMuscle.query.filter_by(muscle=muscle_name).first()
                                if not muscle:
                                    muscle = ExerciseMuscle(muscle=muscle_name)
                                    db.session.add(muscle)
                                    db.session.flush()
                                association_key = (exercise.id, muscle.id)
                                if association_key not in inserted_associations:
                                    # Check if association exists
                                    exists = db.session.query(exercise_muscle_association).filter_by(
                                        exercise_id=exercise.id, muscle_id=muscle.id
                                    ).first()
                                    if not exists:
                                        db.session.execute(
                                            exercise_muscle_association.insert().values(
                                                exercise_id=exercise.id,
                                                muscle_id=muscle.id,
                                                is_primary=True
                                            )
                                        )
                                        inserted_associations.add(association_key)

                        secondary_muscles = clean_muscle_field(row.get('secondaryMuscles', ''))
                        for muscle_name in secondary_muscles:
                            if muscle_name:
                                muscle_name = map_muscle_to_enum(muscle_name)
                                muscle = ExerciseMuscle.query.filter_by(muscle=muscle_name).first()
                                if not muscle:
                                    muscle = ExerciseMuscle(muscle=muscle_name)
                                    db.session.add(muscle)
                                    db.session.flush()
                                association_key = (exercise.id, muscle.id)
                                if association_key not in inserted_associations:
                                    exists = db.session.query(exercise_muscle_association).filter_by(
                                        exercise_id=exercise.id, muscle_id=muscle.id
                                    ).first()
                                    if not exists:
                                        db.session.execute(
                                            exercise_muscle_association.insert().values(
                                                exercise_id=exercise.id,
                                                muscle_id=muscle.id,
                                                is_primary=False
                                            )
                                        )
                                        inserted_associations.add(association_key)

                        db.session.commit()
                        print(f"Added exercise: {row['name']} (row {row_number})")

                    except IntegrityError as e:
                        db.session.rollback()
                        print(f"Error adding exercise at row {row_number} ({row.get('name', 'Unknown')}): {str(e)}")
                    except Exception as e:
                        db.session.rollback()
                        print(f"Unexpected error at row {row_number} ({row.get('name', 'Unknown')}): {str(e)}")

        except UnicodeDecodeError as e:
            print(f"Failed to decode CSV file with {encoding}: {str(e)}")
            print("Trying alternative encodings...")
            for alt_encoding in ['Windows-1252', 'ISO-8859-1', 'latin1']:
                try:
                    with open(csv_file_path, newline='', encoding=alt_encoding, errors='replace') as csvfile:
                        reader = csv.DictReader(csvfile, delimiter=delimiter, fieldnames=None)
                        fieldnames = reader.fieldnames
                        print(f"CSV headers: {fieldnames}")
                        if 'id' in fieldnames:
                            fieldnames = ['exercise_id' if f == 'id' and i == 0 else f for i, f in enumerate(fieldnames)]
                            if fieldnames.count('id') > 0:
                                id_indices = [i for i, f in enumerate(fieldnames) if f == 'id']
                                fieldnames[id_indices[-1]] = 'name_id'
                            reader.fieldnames = fieldnames
                            print(f"Adjusted headers: {fieldnames}")

                        if not expected_columns.issubset(fieldnames):
                            missing = expected_columns - set(fieldnames)
                            print(f"Error: CSV missing columns with {alt_encoding}: {missing}")
                            return

                        row_number = 0
                        for row in reader:
                            row_number += 1
                            try:
                                if not row['exercise_id'] or not row['name']:
                                    print(f"Skipping row {row_number}: Missing exercise_id or name")
                                    continue

                                if row_number in [837, 859, 860]:
                                    print(f"Debug row {row_number}: name={row['name']}, exercise_id={row['exercise_id']}, name_id={row.get('name_id', '')}, primaryMuscles={clean_muscle_field(row.get('primaryMuscles', ''))}, secondaryMuscles={clean_muscle_field(row.get('secondaryMuscles', ''))}")

                                instructions = row.get('instructions', '')
                                try:
                                    instructions_json = json.loads(instructions) if instructions else []
                                    if not isinstance(instructions_json, list):
                                        instructions_json = [instructions_json]
                                    instructions_json = json.dumps(instructions_json)
                                except json.JSONDecodeError:
                                    instructions_json = json.dumps([instructions.strip()]) if instructions else '[]'

                                images = row.get('images', '')
                                try:
                                    images_json = json.loads(images) if images else []
                                    if not isinstance(images_json, list):
                                        images_json = [images_json]
                                    images_json = json.dumps(images_json)
                                except json.JSONDecodeError:
                                    images_json = json.dumps([img.strip() for img in images.split(',') if img.strip()]) if images else '[]'

                                exercise = Exercise(
                                    id=row['exercise_id'],
                                    name=row['name'],
                                    force=row.get('force') or None,
                                    level=row.get('level', 'beginner'),
                                    mechanic=row.get('mechanic') or None,
                                    equipment=row.get('equipment') or None,
                                    category=row.get('category', 'strength'),
                                    instructions=instructions_json,
                                    images=images_json
                                )
                                db.session.add(exercise)
                                db.session.flush()

                                inserted_associations = set()

                                primary_muscles = clean_muscle_field(row.get('primaryMuscles', ''))
                                for muscle_name in primary_muscles:
                                    if muscle_name:
                                        muscle_name = map_muscle_to_enum(muscle_name)
                                        muscle = ExerciseMuscle.query.filter_by(muscle=muscle_name).first()
                                        if not muscle:
                                            muscle = ExerciseMuscle(muscle=muscle_name)
                                            db.session.add(muscle)
                                            db.session.flush()
                                        association_key = (exercise.id, muscle.id)
                                        if association_key not in inserted_associations:
                                            exists = db.session.query(exercise_muscle_association).filter_by(
                                                exercise_id=exercise.id, muscle_id=muscle.id
                                            ).first()
                                            if not exists:
                                                db.session.execute(
                                                    exercise_muscle_association.insert().values(
                                                        exercise_id=exercise.id,
                                                        muscle_id=muscle.id,
                                                        is_primary=True
                                                    )
                                                )
                                                inserted_associations.add(association_key)

                                secondary_muscles = clean_muscle_field(row.get('secondaryMuscles', ''))
                                for muscle_name in secondary_muscles:
                                    if muscle_name:
                                        muscle_name = map_muscle_to_enum(muscle_name)
                                        muscle = ExerciseMuscle.query.filter_by(muscle=muscle_name).first()
                                        if not muscle:
                                            muscle = ExerciseMuscle(muscle=muscle_name)
                                            db.session.add(muscle)
                                            db.session.flush()
                                        association_key = (exercise.id, muscle.id)
                                        if association_key not in inserted_associations:
                                            exists = db.session.query(exercise_muscle_association).filter_by(
                                                exercise_id=exercise.id, muscle_id=muscle.id
                                            ).first()
                                            if not exists:
                                                db.session.execute(
                                                    exercise_muscle_association.insert().values(
                                                        exercise_id=exercise.id,
                                                        muscle_id=muscle.id,
                                                        is_primary=False
                                                    )
                                                )
                                                inserted_associations.add(association_key)

                                db.session.commit()
                                print(f"Added exercise: {row['name']} (row {row_number}) with encoding {alt_encoding}")
                            except IntegrityError as e:
                                db.session.rollback()
                                print(f"Error adding exercise at row {row_number} ({row.get('name', 'Unknown')}): {str(e)}")
                            except Exception as e:
                                db.session.rollback()
                                print(f"Unexpected error at row {row_number} ({row.get('name', 'Unknown')}): {str(e)}")
                        print(f"Successfully processed CSV with encoding {alt_encoding}")
                        return
                except UnicodeDecodeError as e:
                    print(f"Failed with encoding {alt_encoding}: {str(e)}")
            print("All encoding attempts failed. Please check the CSV file encoding.")

if __name__ == '__main__':
    csv_file_path = '/app/exercises.csv'
    seed_exercises(csv_file_path)