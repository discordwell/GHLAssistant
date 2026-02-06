// Initialize SortableJS on all kanban columns for drag-and-drop
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".kanban-cards").forEach(function (el) {
        new Sortable(el, {
            group: "kanban",
            animation: 150,
            ghostClass: "sortable-ghost",
            chosenClass: "sortable-chosen",
            onEnd: function (evt) {
                var candidateId = evt.item.dataset.id;
                var newStage = evt.to.dataset.stage;

                if (!candidateId || !newStage) return;

                // Send stage change via HTMX-style fetch
                var formData = new FormData();
                formData.append("stage", newStage);

                fetch("/board/move/" + candidateId, {
                    method: "POST",
                    body: formData,
                }).then(function (response) {
                    if (!response.ok) {
                        console.error("Failed to move candidate");
                    }
                });
            },
        });
    });
});
