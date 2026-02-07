/**
 * MaxLevel Workflow Visual Editor
 * Bridges Drawflow canvas with backend API via HTMX-style fetch calls.
 */

// ── Drawflow Initialization ──────────────────────────────────────────

const container = document.getElementById("drawflow");
const editor = new Drawflow(container);
editor.reroute = true;
editor.start();

// Map: drawflow node ID → backend step UUID
const nodeToStepId = {};
const stepIdToNode = {};

function esc(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}

// ── Load existing steps ──────────────────────────────────────────────

function loadExistingSteps() {
  stepsData.forEach((step) => {
    const nodeId = addNodeToCanvas(step);
    nodeToStepId[nodeId] = step.id;
    stepIdToNode[step.id] = nodeId;
  });

  // Restore connections after all nodes exist
  setTimeout(() => {
    connectionsData.forEach((conn) => {
      const fromNode = stepIdToNode[conn.from];
      const toNode = stepIdToNode[conn.to];
      if (fromNode && toNode) {
        const outputIdx = conn.type === "true_branch" ? 2 : conn.type === "false_branch" ? 3 : 1;
        try {
          editor.addConnection(fromNode, toNode, `output_${outputIdx}`, "input_1");
        } catch (e) {
          // Connection may already exist
        }
      }
    });
  }, 100);
}

function addNodeToCanvas(step) {
  const outputs = step.step_type === "condition" ? 2 : 1;
  const cssClass = step.step_type;
  const html = `
    <div class="title-box">${esc(step.label || step.action_type || step.step_type)}</div>
    <div class="box">
      <span class="text-xs">${esc(step.step_type)}${step.action_type ? " · " + esc(step.action_type) : ""}</span>
    </div>
  `;
  return editor.addNode(
    step.id,
    1,          // inputs
    outputs,    // outputs
    step.canvas_x,
    step.canvas_y,
    cssClass,
    {},
    html
  );
}

// ── Add new node ─────────────────────────────────────────────────────

async function addNode(stepType, actionType = null) {
  const label = actionType
    ? actionType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : stepType === "condition" ? "If/Else" : "Wait";

  // Save to backend first
  const res = await fetch(`/api/workflows/${workflowId}/steps`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      step_type: stepType,
      action_type: actionType,
      label: label,
      canvas_x: 300 + Math.random() * 200,
      canvas_y: 100 + Math.random() * 200,
    }),
  });
  const step = await res.json();

  // Add to canvas
  const nodeId = addNodeToCanvas(step);
  nodeToStepId[nodeId] = step.id;
  stepIdToNode[step.id] = nodeId;
  updateSaveStatus("Saved");
}

// ── Event handlers ───────────────────────────────────────────────────

// Node moved → save position
editor.on("nodeMoved", async (nodeId) => {
  const stepId = nodeToStepId[nodeId];
  if (!stepId) return;

  const pos = editor.getNodeFromId(nodeId).pos_x;
  const node = editor.getNodeFromId(nodeId);

  await fetch(`/api/steps/${stepId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      canvas_x: node.pos_x,
      canvas_y: node.pos_y,
    }),
  });
  updateSaveStatus("Saved");
});

// Connection created → save to backend
editor.on("connectionCreated", async ({ output_id, input_id, output_class }) => {
  const fromStepId = nodeToStepId[output_id];
  const toStepId = nodeToStepId[input_id];
  if (!fromStepId || !toStepId) return;

  const connType = output_class === "output_2" ? "true_branch"
                 : output_class === "output_3" ? "false_branch"
                 : "next";

  await fetch("/api/connections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      from_step_id: fromStepId,
      to_step_id: toStepId,
      connection_type: connType,
    }),
  });
  updateSaveStatus("Saved");
});

// Connection removed → delete from backend
editor.on("connectionRemoved", async ({ output_id, output_class }) => {
  const fromStepId = nodeToStepId[output_id];
  if (!fromStepId) return;

  const connType = output_class === "output_2" ? "true_branch"
                 : output_class === "output_3" ? "false_branch"
                 : "next";

  await fetch("/api/connections", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      from_step_id: fromStepId,
      connection_type: connType,
    }),
  });
  updateSaveStatus("Saved");
});

// Node removed → delete from backend
editor.on("nodeRemoved", async (nodeId) => {
  const stepId = nodeToStepId[nodeId];
  if (!stepId) return;

  await fetch(`/api/steps/${stepId}`, { method: "DELETE" });
  delete nodeToStepId[nodeId];
  delete stepIdToNode[stepId];
  updateSaveStatus("Saved");
});

// Node selected → open config sidebar
editor.on("nodeSelected", (nodeId) => {
  const stepId = nodeToStepId[nodeId];
  if (stepId) openConfig(stepId);
});

editor.on("nodeUnselected", () => {
  closeConfig();
});

// ── Config sidebar ───────────────────────────────────────────────────

function openConfig(stepId) {
  const sidebar = document.getElementById("step-config");
  sidebar.classList.add("open");

  const content = document.getElementById("step-config-content");
  content.innerHTML = `
    <p class="text-xs text-gray-500 mb-3">Step ID: ${stepId}</p>
    <div class="space-y-3">
      <div>
        <label class="block text-xs text-gray-400 mb-1">Label</label>
        <input type="text" id="cfg-label" class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white"
               onchange="updateStepConfig('${stepId}')">
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">Action Type</label>
        <select id="cfg-action-type" class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white"
                onchange="updateStepConfig('${stepId}')">
          <option value="">Select...</option>
          <option value="send_email">Send Email</option>
          <option value="send_sms">Send SMS</option>
          <option value="add_tag">Add Tag</option>
          <option value="remove_tag">Remove Tag</option>
          <option value="move_opportunity">Move Opportunity</option>
          <option value="create_task">Create Task</option>
          <option value="update_custom_field">Update Custom Field</option>
          <option value="http_webhook">HTTP Webhook</option>
          <option value="add_to_workflow">Add to Workflow</option>
          <option value="delay">Delay</option>
        </select>
      </div>
      <button onclick="deleteStep('${stepId}')"
              class="w-full mt-4 px-3 py-1.5 text-xs bg-red-600/10 text-red-400 border border-red-500/20 rounded-lg hover:bg-red-600/20">
        Delete Step
      </button>
    </div>
  `;

  // Load current values
  loadStepConfig(stepId);
}

async function loadStepConfig(stepId) {
  const steps = await (await fetch(`/api/workflows/${workflowId}/steps`)).json();
  const step = steps.find((s) => s.id === stepId);
  if (!step) return;

  const labelEl = document.getElementById("cfg-label");
  const actionEl = document.getElementById("cfg-action-type");
  if (labelEl) labelEl.value = step.label || "";
  if (actionEl) actionEl.value = step.action_type || "";
}

async function updateStepConfig(stepId) {
  const label = document.getElementById("cfg-label")?.value;
  const actionType = document.getElementById("cfg-action-type")?.value;

  await fetch(`/api/steps/${stepId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, action_type: actionType || null }),
  });
  updateSaveStatus("Saved");
}

async function deleteStep(stepId) {
  const nodeId = stepIdToNode[stepId];
  if (nodeId) editor.removeNodeId(`node-${nodeId}`);
  closeConfig();
}

function closeConfig() {
  document.getElementById("step-config").classList.remove("open");
}

// ── UI helpers ───────────────────────────────────────────────────────

function updateSaveStatus(text) {
  const el = document.getElementById("save-status");
  if (el) {
    el.textContent = text;
    el.classList.add("text-emerald-400");
    setTimeout(() => el.classList.remove("text-emerald-400"), 1500);
  }
}

// ── Initialize ───────────────────────────────────────────────────────
loadExistingSteps();
