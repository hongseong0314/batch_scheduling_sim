from tests.mes_api_support import client


def _ingest_a_batch_and_create_proposal() -> dict:
    client.post("/api/v2/simulation/reset")
    rows = [
        (
            "legacy_mes_equipment",
            {
                "equipment_id": "A_0",
                "operation_id": "A",
                "batch_size": 2,
                "event_time": 1,
                "status": "AVAILABLE",
            },
        ),
        (
            "legacy_mes_wip_unit",
            {
                "unit_id": "WAFER_701",
                "lot_id": "LOT_POLICY_ALPHA",
                "operation_id": "A",
                "task_uid": 701,
                "due_date": 40,
                "material_type": "plastic",
                "color": "red",
                "customer_id": "ALPHA",
                "event_time": 2,
            },
        ),
        (
            "legacy_mes_wip_unit",
            {
                "unit_id": "WAFER_702",
                "lot_id": "LOT_POLICY_ALPHA",
                "operation_id": "A",
                "task_uid": 702,
                "due_date": 41,
                "material_type": "plastic",
                "color": "red",
                "customer_id": "ALPHA",
                "event_time": 3,
            },
        ),
    ]
    for adapter_id, row in rows:
        response = client.post(f"/api/v2/legacy-adapters/{adapter_id}/ingest", json=row)
        assert response.status_code == 200
    response = client.post("/api/v2/digital-twin/recommendation-run", json={"stage": "A"})
    assert response.status_code == 200
    return response.json()


def test_decision_dataset_api_exposes_policy_learning_rows() -> None:
    run = _ingest_a_batch_and_create_proposal()

    response = client.get("/api/v2/ai-dev/decision-dataset")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    row = next(
        item for item in body["items"]
        if item["correlation_id"] == run["correlation_id"]
    )
    assert row["state_source"] == "CANONICAL_TWIN"
    assert row["selected_candidate_id"]
    assert row["candidate_count"] >= 1
    assert row["policy_stack"]["l1_policy_id"] == "L1_FIFO_BASELINE"
    assert row["policy_stack"]["l3_policy_id"] == "L3_CANDIDATE_PORTFOLIO_RULE"
    assert row["action_proposal"]["proposal_id"] == run["action_proposal"]["proposal_id"]
    assert row["workflow"]["current_status"] == "PENDING_REVIEW"
    assert row["learning_label"]["has_legacy_decision"] is False


def test_policy_evaluation_summary_api_counts_decisions_and_proposals() -> None:
    _ingest_a_batch_and_create_proposal()

    response = client.get("/api/v2/ai-dev/policy-evaluation-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["decision_count"] >= 1
    assert body["proposal_count"] >= 1
    assert body["policy_stack"]["l4_policy_id"] == "L4_CYCLE_WEIGHT_RULE"
    assert body["validation_status_counts"]["PASSED"] >= 1
    assert body["workflow_status_counts"]["PENDING_REVIEW"] >= 1
    assert "A" in body["selected_stage_counts"]


def test_action_proposal_workflow_requires_review_before_legacy_submission() -> None:
    run = _ingest_a_batch_and_create_proposal()
    proposal_id = run["action_proposal"]["proposal_id"]

    response = client.get(f"/api/v2/action-proposals/{proposal_id}/workflow")

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"]["proposal_id"] == proposal_id
    assert body["workflow"]["current_status"] == "PENDING_REVIEW"
    assert body["workflow"]["safe_to_submit_to_legacy"] is False
    assert body["workflow"]["direct_equipment_control"] is False


def test_action_proposal_review_persists_in_lifecycle_and_queue() -> None:
    run = _ingest_a_batch_and_create_proposal()
    proposal_id = run["action_proposal"]["proposal_id"]

    review = client.post(
        f"/api/v2/action-proposals/{proposal_id}/reviews",
        json={
            "review_status": "APPROVED",
            "reviewer": "process_engineer",
            "required_role": "PROCESS_ENGINEER",
            "reviewed_at": 100,
            "reason": "safe legacy MES review candidate",
        },
    )
    assert review.status_code == 200
    assert review.json()["item"]["review_status"] == "APPROVED"

    workflow = client.get(f"/api/v2/action-proposals/{proposal_id}/workflow").json()
    assert workflow["workflow"]["current_status"] == "APPROVED_FOR_LEGACY_SUBMISSION"
    assert workflow["workflow"]["safe_to_submit_to_legacy"] is True
    assert workflow["summary"]["latest_review_status"] == "APPROVED"
    assert workflow["review_count"] == 1

    queue = client.get("/api/v2/action-proposals/approval-queue").json()
    item = next(row for row in queue["items"] if row["proposal_id"] == proposal_id)
    assert item["workflow"]["current_status"] == "APPROVED_FOR_LEGACY_SUBMISSION"
    assert item["summary"]["latest_review_status"] == "APPROVED"
