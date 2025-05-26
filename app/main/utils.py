from flask import url_for
import re

def check_onboarding_status(user):
    if not user.name:
        return url_for('main.onboarding_name')
    elif not user.current_weight:
        return url_for('main.onboarding_current_weight')
    elif not user.fitness_goal:
        return url_for('main.onboarding_goal_weight')
    return None  # Onboarding is klaar

def fix_image_path(path):
    path = path.strip().strip('"').strip("'")

    if not path.startswith('img/exercises/'):
        path = f'img/exercises/{path}'

    #getallen als folders
    path = re.sub(r'exercises/(\d+)/(\d+_[^/]+)', r'exercises/\1_\2', path)
    #twee tekstfolders
    path = re.sub(r'exercises/([^/]+)/([^/]+)/(\d+\.jpg)', r'exercises/\1_\2/\3', path)
    #verwijder haakjes
    path = re.sub(r'\(([^)]+)\)', r'\1', path)
    return path

def clean_instruction_text(text):
    return text.replace('\ufffd', '¾')