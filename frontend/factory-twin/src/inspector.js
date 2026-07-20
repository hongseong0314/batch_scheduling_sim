function escapeText(value) {
  return String(value ?? "-")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function valueText(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "-";
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number" && !Number.isInteger(value)) return value.toFixed(3);
  return String(value);
}

export class FactoryInspector {
  constructor(elements) {
    this.root = elements.root;
    this.type = elements.type;
    this.title = elements.title;
    this.body = elements.body;
    this.actions = elements.actions;
    elements.close.onclick = () => this.close();
  }

  show(ref, layoutEntity, stateEntity) {
    const entityType = String(ref.entityType || "entity").toUpperCase();
    const entityId = String(ref.entityId || "-");
    this.type.textContent = entityType;
    this.title.textContent = layoutEntity?.display_name || stateEntity?.equipment_id || stateEntity?.queue_id || stateEntity?.carrier_id || stateEntity?.lot_id || entityId;
    const merged = { ...(layoutEntity || {}), ...(stateEntity || {}) };
    const preferred = this.preferredRows(ref.entityType, merged);
    this.body.innerHTML = preferred.map(([label, value]) => `
      <div class="factory-twin-inspector-row">
        <span>${escapeText(label)}</span>
        <strong>${escapeText(valueText(value))}</strong>
      </div>
    `).join("");
    this.actions.replaceChildren();
    this.actionButtons(ref, merged).forEach(({ label, action }) => {
      const button = document.createElement("button");
      button.className = "button compact";
      button.type = "button";
      button.textContent = label;
      button.onclick = action;
      this.actions.appendChild(button);
    });
    this.root.hidden = false;
  }

  preferredRows(type, entity) {
    const common = [["ID", entity.id || entity.equipment_id || entity.queue_id || entity.task_uid || entity.carrier_id || entity.warehouse_id]];
    if (type === "equipment") return [...common, ["Operation", entity.operation_id], ["Status", entity.status], ["Batch", `${(entity.task_uids || []).length}/${entity.batch_size ?? "-"}`], ["Tasks", entity.task_uids], ["Progress", entity.progress === null ? "indeterminate" : entity.progress], ["Finish time", entity.finish_time], ["Recipe", entity.recipe_summary], ["Health", entity.health_summary], ["Evidence", entity.evidence_source]];
    if (type === "queue") return [...common, ["Operation", entity.operation_id], ["Queue type", entity.queue_type || entity.metadata?.queue_type], ["Exact count", entity.count], ["Visible tasks", entity.visible_task_uids || entity.task_uids]];
    if (type === "task") return [...common, ["Lot", entity.lot_id], ["Customer", entity.customer_id], ["Status", entity.status], ["Operation", entity.operation_id], ["Location", `${entity.location_type || "-"} · ${entity.location_id || "-"}`], ["Carrier", entity.carrier_id], ["Due date", entity.due_date], ["Quality", entity.quality_summary]];
    if (type === "carrier") return [...common, ["Status", entity.status], ["Route", entity.route_id], ["From / to", `${entity.from_operation_id || "-"} -> ${entity.to_operation_id || "-"}`], ["Dispatch / arrival", `${valueText(entity.dispatch_time)} -> ${valueText(entity.arrival_time)}`], ["Tasks", entity.task_uids], ["Progress", entity.progress], ["Transfer", entity.transfer_id]];
    if (type === "warehouse") return [...common, ["Completed", entity.completed_count], ["Visible slots", entity.visible_slots], ["Recent tasks", entity.recent_task_uids]];
    if (type === "operation") return [...common, ["Type", entity.metadata?.operation_type], ["Batch size", entity.metadata?.batch_size], ["Process time", entity.metadata?.process_time], ["Archetype", entity.archetype]];
    if (type === "route") return [...common, ["From", entity.from_operation_id], ["To", entity.to_operation_id], ["Travel time", entity.travel_time]];
    return [...common, ...Object.entries(entity).slice(0, 10)];
  }

  actionButtons(ref, entity) {
    const actions = [];
    if (ref.entityType === "equipment") {
      actions.push({ label: "Machine Detail", action: () => window.openMesMachineDetail?.(ref.entityId) });
      const taskUid = (entity.task_uids || [])[0];
      actions.push({ label: "Assignment Trace", action: () => window.openMesAssignmentTrace?.({ equipmentId: ref.entityId, taskUid }) });
      actions.push({ label: "Genealogy", action: () => window.openMesGenealogy?.({ equipmentId: ref.entityId }) });
    }
    if (ref.entityType === "task") {
      actions.push({ label: "Assignment Trace", action: () => window.openMesAssignmentTrace?.({ taskUid: ref.entityId }) });
      actions.push({ label: "Genealogy", action: () => window.openMesGenealogy?.({ taskUid: ref.entityId }) });
    }
    return actions;
  }

  close() {
    this.root.hidden = true;
  }
}
