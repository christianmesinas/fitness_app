document.addEventListener('DOMContentLoaded', function () {
    function toggleMenu(event) {
        event.preventDefault();
        event.stopPropagation();

        const wrapper = event.currentTarget.parentElement;
        const menu = wrapper.querySelector('.settings-menu');

        document.querySelectorAll('.settings-menu').forEach(m => {
            if (m !== menu) m.style.display = 'none';
        });

        menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
    }

    document.querySelectorAll('.setting-dots-workout').forEach(el => {
        el.addEventListener('click', toggleMenu);
    });

    document.addEventListener('click', () => {
        document.querySelectorAll('.settings-menu').forEach(menu => {
            menu.style.display = 'none';
        });
    });

    document.querySelectorAll('.settings-menu').forEach(menu => {
        menu.addEventListener('click', e => e.stopPropagation());
    });
});
