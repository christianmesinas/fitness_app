console.log('🟢 Archive script is geladen');

document.addEventListener('DOMContentLoaded', function() {
    console.log('🟢 DOM is geladen');

    // Directe click listeners op alle archive links
    const archiveLinks = document.querySelectorAll('.archive-workout');
    console.log('🔍 Gevonden archive links:', archiveLinks.length);

    archiveLinks.forEach((link, index) => {
        console.log(`Archive link ${index}:`, link);
        console.log(`Data workout ID: ${link.getAttribute('data-workout-id')}`);

        link.addEventListener('click', function(e) {
            console.log('🎯 DIRECTE CLICK op archive link!');
            e.preventDefault();
            e.stopPropagation();

            const workoutId = this.getAttribute('data-workout-id');
            console.log('🆔 Workout ID:', workoutId);

            if (!workoutId) {
                console.error('❌ Geen workout ID gevonden!');
                return;
            }

            // Eerst de server request
            console.log('📡 Versturen fetch request...');

            // CSRF token ophalen
            const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content');
            console.log('🔐 CSRF Token:', csrfToken);

            const headers = {
                'Content-Type': 'application/json',
            };

            if (csrfToken) {
                headers['X-CSRFToken'] = csrfToken;
            }

            fetch(`/archive_workout/${workoutId}`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({})
            })
            .then(response => {
                console.log('📨 Response status:', response.status);
                if (response.ok) {
                    return response.json();
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            })
            .then(data => {
                console.log('✅ Response data:', data);
                console.log('✅ Workout succesvol gearchiveerd in database');

                // Nu de card verbergen
                const workoutCard = this.closest('.workout-block');
                if (workoutCard) {
                    console.log('🫥 Verbergen workout card:', workoutCard);

                    // Smooth fade-out animatie
                    workoutCard.style.transition = 'opacity 0.3s ease-out';
                    workoutCard.style.opacity = '0';

                    setTimeout(() => {
                        workoutCard.style.display = 'none';
                        console.log('💀 Card definitief verborgen');
                    }, 300);
                } else {
                    console.error('❌ Kon workout card niet vinden');
                }
            })
            .catch(error => {
                console.error('❌ Fetch error:', error);
                console.error('❌ Workout NIET gearchiveerd - card blijft zichtbaar');
                // Geen card verbergen bij fout
            });
        });
    });
});