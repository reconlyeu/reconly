"""Tests for Templates API routes."""
import pytest


@pytest.mark.api
class TestPromptTemplatesAPI:
    """Test suite for /api/v1/templates/prompt endpoints."""

    def test_list_prompt_templates_only_builtins(self, client):
        """Test listing prompt templates returns only builtins when no user templates exist."""
        response = client.get("/api/v1/templates/prompt")
        assert response.status_code == 200
        data = response.json()
        # All templates should be builtin (seeded by app startup)
        user_templates = [t for t in data if t.get("origin") == "user"]
        assert len(user_templates) == 0

    def test_list_prompt_templates(self, client, sample_prompt_template):
        """Test listing prompt templates includes user-created template."""
        response = client.get("/api/v1/templates/prompt")
        assert response.status_code == 200
        data = response.json()
        # Find our test template in the list
        test_template = next((t for t in data if t["name"] == "Test Prompt Template"), None)
        assert test_template is not None
        assert test_template["system_prompt"] == "You are a helpful assistant."
        assert test_template["user_prompt_template"] == "Summarize: {{ content }}"

    def test_create_prompt_template(self, client):
        """Test creating a new prompt template."""
        template_data = {
            "name": "New Summary Template",
            "description": "Creates brief summaries",
            "system_prompt": "You are an expert summarizer.",
            "user_prompt_template": "Please summarize the following in {{ language }}:\n\n{{ content }}",
            "language": "en",
            "target_length": 200
        }
        response = client.post("/api/v1/templates/prompt", json=template_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Summary Template"
        assert data["system_prompt"] == "You are an expert summarizer."
        assert data["user_prompt_template"] == "Please summarize the following in {{ language }}:\n\n{{ content }}"
        assert data["target_length"] == 200
        assert data["id"] is not None

    def test_create_prompt_template_requires_correct_fields(self, client):
        """Test that prompt template creation requires system_prompt and user_prompt_template."""
        # Missing system_prompt
        response = client.post("/api/v1/templates/prompt", json={
            "name": "Test",
            "user_prompt_template": "Test"
        })
        assert response.status_code == 422

        # Missing user_prompt_template
        response = client.post("/api/v1/templates/prompt", json={
            "name": "Test",
            "system_prompt": "Test"
        })
        assert response.status_code == 422

        # Old field name should not work
        response = client.post("/api/v1/templates/prompt", json={
            "name": "Test",
            "template_content": "This is old field"
        })
        assert response.status_code == 422

    def test_get_prompt_template(self, client, sample_prompt_template):
        """Test getting a specific prompt template."""
        response = client.get(f"/api/v1/templates/prompt/{sample_prompt_template.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_prompt_template.id
        assert data["name"] == "Test Prompt Template"

    def test_get_prompt_template_not_found(self, client):
        """Test getting non-existent prompt template."""
        response = client.get("/api/v1/templates/prompt/99999")
        assert response.status_code == 404

    def test_update_prompt_template(self, client, sample_prompt_template):
        """Test updating a prompt template."""
        update_data = {
            "name": "Updated Template",
            "target_length": 300
        }
        response = client.put(f"/api/v1/templates/prompt/{sample_prompt_template.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Template"
        assert data["target_length"] == 300

    def test_delete_prompt_template(self, client, sample_prompt_template):
        """Test deleting a prompt template."""
        response = client.delete(f"/api/v1/templates/prompt/{sample_prompt_template.id}")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get(f"/api/v1/templates/prompt/{sample_prompt_template.id}")
        assert response.status_code == 404


@pytest.mark.api
class TestReportTemplatesAPI:
    """Test suite for /api/v1/templates/report endpoints."""

    def test_list_report_templates_only_builtins(self, client):
        """Test listing report templates returns only builtins when no user templates exist."""
        response = client.get("/api/v1/templates/report")
        assert response.status_code == 200
        data = response.json()
        # All templates should be builtin (seeded by app startup)
        user_templates = [t for t in data if t.get("origin") == "user"]
        assert len(user_templates) == 0

    def test_list_report_templates(self, client, sample_report_template):
        """Test listing report templates includes user-created template."""
        response = client.get("/api/v1/templates/report")
        assert response.status_code == 200
        data = response.json()
        # Find our test template in the list
        test_template = next((t for t in data if t["name"] == "Test Report Template"), None)
        assert test_template is not None
        assert test_template["format"] == "markdown"
        assert test_template["template_content"] == "# Report\n\n{content}"

    def test_create_report_template(self, client):
        """Test creating a new report template."""
        template_data = {
            "name": "New Report Template",
            "description": "HTML report format",
            "format": "html",
            "template_content": "<html><body>{content}</body></html>"
        }
        response = client.post("/api/v1/templates/report", json=template_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Report Template"
        assert data["format"] == "html"
        assert data["id"] is not None

    def test_create_report_template_validation(self, client):
        """Test report template validation."""
        # Invalid format
        response = client.post("/api/v1/templates/report", json={
            "name": "Test",
            "format": "invalid_format",
            "template_content": "test"
        })
        assert response.status_code == 422

    def test_get_report_template(self, client, sample_report_template):
        """Test getting a specific report template."""
        response = client.get(f"/api/v1/templates/report/{sample_report_template.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_report_template.id

    def test_update_report_template(self, client, sample_report_template):
        """Test updating a report template."""
        update_data = {
            "name": "Updated Report",
            "format": "text"
        }
        response = client.put(f"/api/v1/templates/report/{sample_report_template.id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Report"
        assert data["format"] == "text"

    def test_delete_report_template(self, client, sample_report_template):
        """Test deleting a report template."""
        response = client.delete(f"/api/v1/templates/report/{sample_report_template.id}")
        assert response.status_code == 204


@pytest.mark.api
class TestTemplateEndpointPaths:
    """Test that template endpoints use correct paths (/templates/prompt, /templates/report)."""

    def test_old_prompt_templates_path_not_found(self, client):
        """Verify old /prompt-templates path does NOT work."""
        response = client.get("/api/v1/prompt-templates")
        assert response.status_code == 404

    def test_old_report_templates_path_not_found(self, client):
        """Verify old /report-templates path does NOT work."""
        response = client.get("/api/v1/report-templates")
        assert response.status_code == 404

    def test_correct_prompt_templates_path_works(self, client):
        """Verify correct /templates/prompt path works."""
        response = client.get("/api/v1/templates/prompt")
        assert response.status_code == 200

    def test_correct_report_templates_path_works(self, client):
        """Verify correct /templates/report path works."""
        response = client.get("/api/v1/templates/report")
        assert response.status_code == 200
