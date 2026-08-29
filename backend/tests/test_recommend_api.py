"""Unit tests for POST /api/recommend endpoint."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_recommend_endpoint_returns_200_with_default_payload():
    response = client.post(
        "/api/recommend",
        json={
            "product_type": "b2b_analytics",
            "product_size": "smb",
            "team_size": 15,
            "licensed_skills": ["postgres_enterprise", "redis_enterprise", "aws_certified_devops"],
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["recommendation_id"].startswith("rec_")
    assert "generated_at" in data
    assert data["input_context"]["product_type"] == "b2b_analytics"
    assert data["input_context"]["product_size"] == "smb"

    # Overall metrics
    metrics = data["overall_metrics"]
    assert 0 <= metrics["composite_fit_score"] <= 100
    assert 0 <= metrics["licensing_coverage_percent"] <= 100
    assert metrics["estimated_monthly_infra_min"] < metrics["estimated_monthly_infra_max"]
    assert metrics["time_to_mvp_weeks"] > 0

    # Stack categories
    categories = data["stack_categories"]
    assert "frontend" in categories
    assert "backend" in categories
    assert "database" in categories
    assert "caching" in categories
    assert "devops" in categories
    assert "observability" in categories

    for cat_name, cat_data in categories.items():
        assert cat_data["technology"]
        assert 0 <= cat_data["fit_score"] <= 100
        assert cat_data["license_flag"] in ["OK", "NEEDS_LICENSE", "INCOMPATIBLE"]
        assert len(cat_data["alternatives"]) > 0

    # Actionable steps
    steps = data["actionable_next_steps"]
    assert len(steps) == 3
    assert steps[0]["phase"] == "Foundation"


def test_recommend_endpoint_scales_cost_for_mvp_vs_enterprise():
    resp_mvp = client.post(
        "/api/recommend",
        json={"product_type": "consumer_mobile", "product_size": "mvp"},
    )
    assert resp_mvp.status_code == 200
    data_mvp = resp_mvp.json()

    resp_ent = client.post(
        "/api/recommend",
        json={"product_type": "consumer_mobile", "product_size": "enterprise"},
    )
    assert resp_ent.status_code == 200
    data_ent = resp_ent.json()

    assert data_mvp["overall_metrics"]["estimated_monthly_infra_max"] < data_ent["overall_metrics"]["estimated_monthly_infra_max"]
    assert data_mvp["overall_metrics"]["time_to_mvp_weeks"] < data_ent["overall_metrics"]["time_to_mvp_weeks"]
