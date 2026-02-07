document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".kanban-cards").forEach(function (el) {
        new Sortable(el, {
            group: "kanban",
            animation: 150,
            ghostClass: "sortable-ghost",
            chosenClass: "sortable-chosen",
            onEnd: function (evt) {
                var oppId = evt.item.dataset.id;
                var newStageId = evt.to.dataset.stageId;

                if (!oppId || !newStageId) return;

                // Extract slug from current URL: /loc/{slug}/pipelines/...
                var pathParts = window.location.pathname.split("/");
                var slug = pathParts[2];

                var formData = new FormData();
                formData.append("stage_id", newStageId);

                fetch("/loc/" + slug + "/opportunities/" + oppId + "/move", {
                    method: "POST",
                    body: formData,
                }).then(function (response) {
                    if (!response.ok) {
                        console.error("Failed to move opportunity");
                    }
                });
            },
        });
    });
});
