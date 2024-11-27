import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_llm_config():
    return {
        "temperature": 0.7,
        "model": "gpt-4",
        "api_key": "test_key"
    }

@pytest.fixture
def mock_autogen_bot():
    bot = Mock()
    bot.send = Mock()
    bot.get_response = Mock(return_value="test response")
    return bot 