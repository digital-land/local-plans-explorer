document.addEventListener('DOMContentLoaded', function() {
    // Find all remove links
    const removeLinks = document.querySelectorAll('.js-remove-event');

    removeLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            // Get the references from data attributes
            const eventRef = this.dataset.eventReference;
            const timetableRef = this.dataset.timetableReference;
            const planRef = this.dataset.planReference;

            // Show confirmation dialog
            if (confirm("This will set the end date of the event so it will be removed from the timetable, but it won't be deleted. Ok to continue?")) {
                // If confirmed, redirect to the remove URL
                window.location.href = `/local-plan/${planRef}/timetable/${timetableRef}/event/${eventRef}/remove`;
            }
        });
    });
});
