document.addEventListener('DOMContentLoaded', function() {
    // Find all delete links
    const deleteLinks = document.querySelectorAll('.js-delete-event');

    deleteLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            // Get the references from data attributes
            const eventRef = this.dataset.eventReference;
            const timetableRef = this.dataset.timetableReference;
            const planRef = this.dataset.planReference;

            // Show confirmation dialog
            if (confirm('Are you sure you want to delete this event?')) {
                // If confirmed, redirect to the delete URL
                window.location.href = `/local-plan/${planRef}/timetable/${timetableRef}/event/${eventRef}/delete`;
            }
        });
    });
});
