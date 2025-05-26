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

    path = re.sub(r'exercises/(\d+)/(\d+_[^/]+)', r'exercises/\1_\2', path)

    path = re.sub(r'exercises/([^/]+)/([^/]+)/(\d+\.jpg)', r'exercises/\1_\2/\3', path)

    return path


