from flask import url_for

def check_onboarding_status(user):
    if not user.name:
        return url_for('main.onboarding_name')
    elif not user.current_weight:
        return url_for('main.onboarding_current_weight')
    elif not user.fitness_goal:
        return url_for('main.onboarding_goal_weight')
    return None  # Onboarding is klaar

