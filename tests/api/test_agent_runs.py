"""Tests for Agent Runs API routes.

Tests cover:
- GET /api/v1/agent-runs - List agent runs
- GET /api/v1/agent-runs/capabilities - Get agent capabilities
- GET /api/v1/agent-runs/{run_id} - Get specific agent run
- Response structure including research strategy fields
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from reconly_core.database.models import AgentRun, Source


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_agent_source(test_db):
    """Create a sample agent source for testing."""
    source = Source(
        name="Test Agent Source",
        type="agent",
        url="What are the latest developments in AI?",
        enabled=True,
        config={"research_strategy": "simple"},
    )
    test_db.add(source)
    test_db.commit()
    test_db.refresh(source)
    return source


@pytest.fixture
def sample_agent_run(test_db, sample_agent_source):
    """Create a sample completed agent run."""
    agent_run = AgentRun(
        source_id=sample_agent_source.id,
        prompt="What are the latest developments in AI?",
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=2),
        completed_at=datetime.utcnow(),
        iterations=3,
        tool_calls=[
            {"tool": "web_search", "input": {"query": "AI developments 2024"}},
            {"tool": "web_fetch", "input": {"url": "https://example.com"}},
        ],
        sources_consulted=["https://example.com/1", "https://example.com/2"],
        result_title="AI Developments in 2024",
        result_content="# AI Developments\n\nFindings here...",
        tokens_in=500,
        tokens_out=200,
        estimated_cost=0.01,
        trace_id="test-trace-123",
        created_at=datetime.utcnow() - timedelta(minutes=2),
        extra_data={"research_strategy": "simple"},
    )
    test_db.add(agent_run)
    test_db.commit()
    test_db.refresh(agent_run)
    return agent_run


@pytest.fixture
def sample_comprehensive_agent_run(test_db, sample_agent_source):
    """Create a sample comprehensive strategy agent run."""
    agent_run = AgentRun(
        source_id=sample_agent_source.id,
        prompt="Comprehensive research on quantum computing",
        status="completed",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        completed_at=datetime.utcnow(),
        iterations=5,
        tool_calls=[
            {"tool": "gpt_researcher_subtopics", "input": {"count": 3}, "output": "A, B, C"},
            {"tool": "gpt_researcher_web_research", "input": {"sources_explored": 15}},
        ],
        sources_consulted=[f"https://example.com/{i}" for i in range(10)],
        result_title="Quantum Computing Research",
        result_content="# Comprehensive Analysis\n\nDetailed findings...",
        tokens_in=2000,
        tokens_out=800,
        estimated_cost=0.50,
        trace_id="test-trace-456",
        created_at=datetime.utcnow() - timedelta(minutes=5),
        extra_data={
            "research_strategy": "comprehensive",
            "subtopics": ["Topic A", "Topic B", "Topic C"],
            "report_format": "APA",
            "source_count": 10,
        },
    )
    test_db.add(agent_run)
    test_db.commit()
    test_db.refresh(agent_run)
    return agent_run


@pytest.fixture
def sample_failed_agent_run(test_db, sample_agent_source):
    """Create a sample failed agent run."""
    agent_run = AgentRun(
        source_id=sample_agent_source.id,
        prompt="Research that will fail",
        status="failed",
        started_at=datetime.utcnow() - timedelta(minutes=1),
        completed_at=datetime.utcnow(),
        iterations=0,
        tokens_in=0,
        tokens_out=0,
        estimated_cost=0.0,
        error_log="Research failed: timeout",
        trace_id="test-trace-failed",
        created_at=datetime.utcnow() - timedelta(minutes=1),
        extra_data={"research_strategy": "simple"},
    )
    test_db.add(agent_run)
    test_db.commit()
    test_db.refresh(agent_run)
    return agent_run


# =============================================================================
# List Agent Runs Tests
# =============================================================================


@pytest.mark.api
class TestListAgentRuns:
    """Tests for GET /api/v1/agent-runs endpoint."""

    def test_list_agent_runs_empty(self, client):
        """Test listing agent runs when none exist."""
        response = client.get("/api/v1/agent-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_agent_runs(self, client, sample_agent_run):
        """Test listing agent runs returns data."""
        response = client.get("/api/v1/agent-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_agent_runs_includes_source_name(self, client, sample_agent_run):
        """Test that response includes source_name."""
        response = client.get("/api/v1/agent-runs")
        assert response.status_code == 200
        data = response.json()
        run = data["items"][0]
        assert "source_name" in run
        assert run["source_name"] == "Test Agent Source"

    def test_list_agent_runs_filter_by_source_id(
        self, client, sample_agent_run, sample_agent_source
    ):
        """Test filtering by source_id."""
        response = client.get(f"/api/v1/agent-runs?source_id={sample_agent_source.id}")
        assert response.status_code == 200
        data = response.json()
        assert all(run["source_id"] == sample_agent_source.id for run in data["items"])

    def test_list_agent_runs_filter_by_status(self, client, sample_agent_run, sample_failed_agent_run):
        """Test filtering by status."""
        response = client.get("/api/v1/agent-runs?status=completed")
        assert response.status_code == 200
        data = response.json()
        assert all(run["status"] == "completed" for run in data["items"])

    def test_list_agent_runs_pagination(self, client, test_db, sample_agent_source):
        """Test pagination with limit and offset."""
        # Create multiple runs
        for i in range(5):
            run = AgentRun(
                source_id=sample_agent_source.id,
                prompt=f"Research topic {i}",
                status="completed",
                iterations=1,
                tokens_in=100,
                tokens_out=50,
                trace_id=f"trace-{i}",
                created_at=datetime.utcnow() - timedelta(hours=i),
            )
            test_db.add(run)
        test_db.commit()

        # Test limit
        response = client.get("/api/v1/agent-runs?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

        # Test offset
        response = client.get("/api/v1/agent-runs?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2


# =============================================================================
# Get Agent Run Tests
# =============================================================================


@pytest.mark.api
class TestGetAgentRun:
    """Tests for GET /api/v1/agent-runs/{run_id} endpoint."""

    def test_get_agent_run(self, client, sample_agent_run):
        """Test getting a specific agent run."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_agent_run.id
        assert data["prompt"] == sample_agent_run.prompt
        assert data["status"] == "completed"

    def test_get_agent_run_not_found(self, client):
        """Test getting non-existent agent run."""
        response = client.get("/api/v1/agent-runs/99999")
        assert response.status_code == 404

    def test_get_agent_run_includes_duration(self, client, sample_agent_run):
        """Test that response includes calculated duration_seconds."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "duration_seconds" in data
        assert data["duration_seconds"] is not None
        assert data["duration_seconds"] > 0


# =============================================================================
# Agent Run Response Structure Tests
# =============================================================================


@pytest.mark.api
class TestAgentRunResponseStructure:
    """Tests for AgentRunResponse including new strategy fields."""

    def test_response_includes_research_strategy(self, client, sample_agent_run):
        """Test that response includes research_strategy field."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "research_strategy" in data
        assert data["research_strategy"] == "simple"

    def test_response_comprehensive_includes_subtopics(
        self, client, sample_comprehensive_agent_run
    ):
        """Test that comprehensive run includes subtopics."""
        response = client.get(f"/api/v1/agent-runs/{sample_comprehensive_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["research_strategy"] == "comprehensive"
        assert "subtopics" in data
        assert data["subtopics"] is not None
        assert len(data["subtopics"]) == 3

    def test_response_includes_report_format(self, client, sample_comprehensive_agent_run):
        """Test that response includes report_format for comprehensive runs."""
        response = client.get(f"/api/v1/agent-runs/{sample_comprehensive_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "report_format" in data
        assert data["report_format"] == "APA"

    def test_response_includes_source_count(self, client, sample_comprehensive_agent_run):
        """Test that response includes source_count."""
        response = client.get(f"/api/v1/agent-runs/{sample_comprehensive_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "source_count" in data
        assert data["source_count"] == 10

    def test_response_includes_tool_calls(self, client, sample_agent_run):
        """Test that response includes tool_calls list."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "tool_calls" in data
        assert isinstance(data["tool_calls"], list)
        assert len(data["tool_calls"]) > 0

    def test_response_includes_sources_consulted(self, client, sample_agent_run):
        """Test that response includes sources_consulted list."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "sources_consulted" in data
        assert isinstance(data["sources_consulted"], list)

    def test_response_includes_result_fields(self, client, sample_agent_run):
        """Test that response includes result_title and result_content."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert "result_title" in data
        assert "result_content" in data
        assert data["result_title"] == "AI Developments in 2024"

    def test_failed_run_includes_error_log(self, client, sample_failed_agent_run):
        """Test that failed runs include error_log."""
        response = client.get(f"/api/v1/agent-runs/{sample_failed_agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "error_log" in data
        assert data["error_log"] is not None
        assert "timeout" in data["error_log"]


# =============================================================================
# Capabilities Endpoint Tests
# =============================================================================


@pytest.mark.api
class TestAgentCapabilities:
    """Tests for GET /api/v1/agent-runs/capabilities endpoint."""

    def test_get_capabilities_structure(self, client):
        """Test that capabilities endpoint returns correct structure."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=False,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            # Check top-level fields
            assert "strategies" in data
            assert "gpt_researcher_installed" in data
            assert "search_providers" in data
            assert "configured_search_provider" in data

    def test_get_capabilities_strategies(self, client):
        """Test that capabilities includes all strategies."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=False,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            strategies = data["strategies"]
            assert "simple" in strategies
            assert "comprehensive" in strategies
            assert "deep" in strategies

    def test_get_capabilities_simple_always_available(self, client):
        """Test that 'simple' strategy is always available."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=False,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            simple = data["strategies"]["simple"]
            assert simple["available"] is True

    def test_get_capabilities_gpt_researcher_not_installed(self, client):
        """Test capabilities when GPT Researcher is not installed."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=False,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            assert data["gpt_researcher_installed"] is False
            assert data["strategies"]["comprehensive"]["available"] is False
            assert data["strategies"]["deep"]["available"] is False

    def test_get_capabilities_gpt_researcher_installed(self, client):
        """Test capabilities when GPT Researcher is installed."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=True,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            assert data["gpt_researcher_installed"] is True
            assert data["strategies"]["comprehensive"]["available"] is True
            assert data["strategies"]["deep"]["available"] is True

    def test_get_capabilities_strategy_info_fields(self, client):
        """Test that strategy info includes all required fields."""
        with patch(
            "reconly_core.agents.capabilities.is_gpt_researcher_installed",
            return_value=False,
        ):
            response = client.get("/api/v1/agent-runs/capabilities")
            assert response.status_code == 200
            data = response.json()

            for strategy_name, strategy_info in data["strategies"].items():
                assert "available" in strategy_info, f"Missing 'available' for {strategy_name}"
                assert "description" in strategy_info, f"Missing 'description' for {strategy_name}"
                assert "estimated_duration_seconds" in strategy_info, f"Missing duration for {strategy_name}"
                assert "requires_api_key" in strategy_info, f"Missing 'requires_api_key' for {strategy_name}"

    def test_get_capabilities_search_providers(self, client):
        """Test that capabilities includes search providers list."""
        response = client.get("/api/v1/agent-runs/capabilities")
        assert response.status_code == 200
        data = response.json()

        assert "search_providers" in data
        assert isinstance(data["search_providers"], list)
        # Should have at least duckduckgo available
        assert "duckduckgo" in data["search_providers"]

    def test_get_capabilities_configured_search_provider(self, client):
        """Test that capabilities includes configured search provider."""
        response = client.get("/api/v1/agent-runs/capabilities")
        assert response.status_code == 200
        data = response.json()

        assert "configured_search_provider" in data
        # Should be one of the available providers or None
        if data["configured_search_provider"] is not None:
            assert data["configured_search_provider"] in data["search_providers"]


# =============================================================================
# Response Model Tests
# =============================================================================


@pytest.mark.api
class TestAgentRunResponseModel:
    """Tests for AgentRunResponse Pydantic model behavior."""

    def test_response_serialization(self, client, sample_agent_run):
        """Test that response serializes correctly."""
        response = client.get(f"/api/v1/agent-runs/{sample_agent_run.id}")
        assert response.status_code == 200

        # Should be valid JSON
        data = response.json()

        # Datetime fields should be ISO format strings
        assert isinstance(data["created_at"], str)
        if data["started_at"]:
            assert isinstance(data["started_at"], str)
        if data["completed_at"]:
            assert isinstance(data["completed_at"], str)

    def test_list_response_structure(self, client, sample_agent_run):
        """Test that list response has correct structure."""
        response = client.get("/api/v1/agent-runs")
        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_response_defaults_research_strategy(self, client, test_db, sample_agent_source):
        """Test that response defaults research_strategy to 'simple' if not in extra_data."""
        # Create run without research_strategy in extra_data
        agent_run = AgentRun(
            source_id=sample_agent_source.id,
            prompt="Test prompt",
            status="completed",
            iterations=1,
            tokens_in=100,
            tokens_out=50,
            trace_id="test-trace-default",
            created_at=datetime.utcnow(),
            extra_data={},  # No research_strategy
        )
        test_db.add(agent_run)
        test_db.commit()
        test_db.refresh(agent_run)

        response = client.get(f"/api/v1/agent-runs/{agent_run.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["research_strategy"] == "simple"  # Should default to simple
