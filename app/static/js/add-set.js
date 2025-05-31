

document.addEventListener('DOMContentLoaded', function() {
    // Add set functionality
document.querySelectorAll('.active-workout-btn').forEach(button => {
        const action = button.dataset.action;

     if (action === 'add') {
            button.addEventListener('click', function(event) {
                event.preventDefault();
                const workoutBlock = this.closest('.active-workout-block');
                const wpeId = workoutBlock.dataset.wpeId;
                const setSection = workoutBlock.querySelector('.set-section');
                const sets = setSection.querySelectorAll('.active-workout-set');
                const setNum = sets.length;

                const newSet = document.createElement('div');
                newSet.className = 'active-workout-set';
                newSet.innerHTML = `
                    <input type="number" name="reps_${wpeId}_${setNum}" min="1" step="1" placeholder="reps" class="set-input">
                    <input type="number" name="weight_${wpeId}_${setNum}" min="0" step="0.1" placeholder="KG" class="set-input">
                    <label class="custom-checkbox">
                        <input type="checkbox" name="completed_${wpeId}_${setNum}">
                        <span class="checkmark"></span>
                    </label>
                `;
                setSection.appendChild(newSet);

                // Auto-save when inputs change
                const inputs = newSet.querySelectorAll('.set-input');
                inputs.forEach(input => {
                    input.addEventListener('change', function() {
                        saveSetToDatabase(wpeId, setNum, newSet);
                    });
                });

                // Auto-save when checkbox is checked
                const checkbox = newSet.querySelector('input[type="checkbox"]');
                checkbox.addEventListener('change', function() {
                    if (this.checked) {
                        saveSetToDatabase(wpeId, setNum, newSet);
                    }
                });
            });
        }

        // Complete all functionality
    if (action === 'complete') {
            button.addEventListener('click', function(event) {
                event.preventDefault();
                const workoutBlock = this.closest('.active-workout-block');
                const checkboxes = workoutBlock.querySelectorAll('.custom-checkbox input[type="checkbox"]');
                const wpeId = workoutBlock.dataset.wpeId;

                checkboxes.forEach((checkbox, index) => {
                    checkbox.checked = true;
                    const setElement = checkbox.closest('.active-workout-set');
                    saveSetToDatabase(wpeId, index, setElement);
                });
                updateAddSetButtonVisibility(workoutBlock);

            });
        }
    });
});

// Function to save individual set to database
async function saveSetToDatabase(wpeId, setNum, setElement) {
    const repsInput = setElement.querySelector(`input[name="reps_${wpeId}_${setNum}"]`);
    const weightInput = setElement.querySelector(`input[name="weight_${wpeId}_${setNum}"]`);
    const completedInput = setElement.querySelector(`input[name="completed_${wpeId}_${setNum}"]`);

    const reps = parseFloat(repsInput.value) || 0;
    const weight = parseFloat(weightInput.value) || 0;
    const completed = completedInput.checked;

    // Only save if the set is completed and has valid data
    if (completed && reps > 0) {
        try {
            const response = await fetch('/save_set', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').getAttribute('content')
                },
                body: JSON.stringify({
                    wpe_id: wpeId,
                    set_number: setNum,
                    reps: reps,
                    weight: weight,
                    completed: completed
                })
            });

            const data = await response.json();
            if (data.success) {
                // Visual feedback
                setElement.classList.add('set-saved');
                console.log('Set saved successfully');
            } else {
                console.error('Failed to save set:', data.message);
            }
        } catch (error) {
            console.error('Error saving set:', error);
        }
    }
    setElement.classList.add('set-saved');
    updateAddSetButtonVisibility(setElement.closest('.active-workout-block'));

}

// Function to remove a set
function removeSet(button) {
    const setElement = button.closest('.active-workout-set');
    setElement.remove();
}
function updateAddSetButtonVisibility(workoutBlock) {
    const checkboxes = workoutBlock.querySelectorAll('.custom-checkbox input[type="checkbox"]');
    const allCompleted = [...checkboxes].every(cb => cb.checked);
    const addSetBtn = workoutBlock.querySelector('.active-workout-btn');

    if (addSetBtn && addSetBtn.textContent.trim() === 'Add set') {
        addSetBtn.style.display = allCompleted ? 'none' : 'inline-block';
    }
}


// Function to save entire workout
async function saveWorkout(planId) {
    try {
        const response = await fetch(`/save_workout/${planId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').getAttribute('content')
            }
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = '/index';
        } else {
            alert('Failed to save workout: ' + data.message);
        }
    } catch (error) {
        console.error('Error saving workout:', error);
        alert('Error saving workout');
    }
}