from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import ValidationError


def _response(data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    response.json.return_value = data
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


class TestJSearchClient:
    def test_retries_one_transient_timeout_with_sixty_second_timeout(self):
        from app.services import api_aggregator

        response = _response(
            {
                "status": "OK",
                "request_id": "request-123",
                "data": [{"job_id": "job-1"}],
            }
        )

        with (
            patch.object(api_aggregator.settings, "jsearchapi_key", "test-key"),
            patch.object(api_aggregator.settings, "jsearch_num_pages", 10),
            patch.object(api_aggregator.settings, "api_request_timeout_seconds", 60),
            patch.object(api_aggregator.settings, "api_request_delay_seconds", 0),
            patch("requests.Session.get", side_effect=[requests.ReadTimeout(), response]) as get,
            patch("app.services.api_aggregator.time.sleep"),
        ):
            jobs = api_aggregator.JSearchClient().search("data", "New York")

        assert jobs == [{"job_id": "job-1"}]
        assert get.call_count == 2
        assert get.call_args.kwargs["timeout"] == 60
        assert get.call_args.kwargs["params"] == {"query": "data New York", "num_pages": 10}

    def test_does_not_retry_http_errors(self):
        from app.services import api_aggregator

        response = _response({"error": "bad request"}, status_code=400)

        with (
            patch.object(api_aggregator.settings, "jsearchapi_key", "test-key"),
            patch.object(api_aggregator.settings, "jsearch_num_pages", 10),
            patch.object(api_aggregator.settings, "api_request_timeout_seconds", 60),
            patch("requests.Session.get", return_value=response) as get,
        ):
            with pytest.raises(requests.HTTPError):
                api_aggregator.JSearchClient().search("data", "New York")

        assert get.call_count == 1

    def test_retries_one_transient_server_error(self):
        from app.services import api_aggregator

        response = _response({"data": [{"job_id": "job-1"}]})
        server_error = _response({"error": "temporarily unavailable"}, status_code=503)

        with (
            patch.object(api_aggregator.settings, "jsearchapi_key", "test-key"),
            patch.object(api_aggregator.settings, "jsearch_num_pages", 10),
            patch.object(api_aggregator.settings, "api_request_timeout_seconds", 60),
            patch.object(api_aggregator.settings, "api_request_delay_seconds", 0),
            patch("requests.Session.get", side_effect=[server_error, response]) as get,
            patch("app.services.api_aggregator.time.sleep"),
        ):
            jobs = api_aggregator.JSearchClient().search("data", "New York")

        assert jobs == [{"job_id": "job-1"}]
        assert get.call_count == 2


def test_api_request_timeout_cannot_exceed_one_minute():
    from app.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(api_request_timeout_seconds=61)
