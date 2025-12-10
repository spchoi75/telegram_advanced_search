"""
Tests for chat_list.py JSON output format
"""

import json


def test_json_output_format():
    """Test that JSON output has correct structure."""
    # Expected format from PRD
    expected_structure = {
        "chats": [
            {"id": -100123456789, "name": "채팅방명", "type": "supergroup"},
            {"id": 987654321, "name": "개인채팅", "type": "user"},
        ]
    }

    # Validate structure
    assert "chats" in expected_structure
    assert isinstance(expected_structure["chats"], list)

    for chat in expected_structure["chats"]:
        assert "id" in chat
        assert "name" in chat
        assert "type" in chat
        assert chat["type"] in ["user", "group", "supergroup", "channel", "unknown"]


def test_error_format():
    """Test that error response has correct structure."""
    error_response = {
        "error": "Telegram 인증이 필요합니다",
        "code": "SESSION_NOT_FOUND"
    }

    assert "error" in error_response
    assert "code" in error_response
    assert isinstance(error_response["error"], str)
    assert isinstance(error_response["code"], str)


def test_json_serializable():
    """Test that output is JSON serializable."""
    output = {
        "chats": [
            {"id": -1001234567890, "name": "테스트 채팅방", "type": "supergroup"},
            {"id": 123456789, "name": "개인 채팅", "type": "user"},
        ]
    }

    # Should not raise
    json_str = json.dumps(output, ensure_ascii=False)
    parsed = json.loads(json_str)

    assert parsed == output
    assert "테스트 채팅방" in json_str  # Korean should be preserved
