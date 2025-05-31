document.querySelectorAll('.active-workout-btn').forEach(button => {
    if (button.textContent.trim() === 'Add set') {
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
                <input type="number" name="reps_${wpeId}_${setNum}" min="1" step="1" placeholder=" reps">
                <input type="number" name="weight_${wpeId}_${setNum}" min="0" step="0.1" placeholder=" KG">
                <label class="custom-checkbox">
                    <input type="checkbox" name="completed_${wpeId}_${setNum}">
                    <span class="checkmark"></span>
                </label>
            `;
            setSection.appendChild(newSet);
        });
    }
});

if (button.textContent.trim() === 'Complete all') {
    button.addEventListener('click', function(event) {
        event.preventDefault();
        const workoutBlock = this.closest('.active-workout-block');
        const checkboxes = workoutBlock.querySelectorAll('.custom-checkbox input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
    });
}