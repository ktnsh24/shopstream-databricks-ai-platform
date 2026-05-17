def test_visualize_happy_path(client, mock_agent):
    mock_agent.return_value = "Daily revenue trend: steady growth over last 30 days."
    response = client.post("/visualize", json={"question": "Show revenue trend"})
    assert response.status_code == 200
    assert "answer" in response.json()


def test_visualize_agent_error_returns_502(client, mock_agent):
    mock_agent.side_effect = Exception("agent error")
    response = client.post("/visualize", json={"question": "Show revenue trend"})
    assert response.status_code == 502


def test_visualize_missing_question_returns_422(client):
    response = client.post("/visualize", json={})
    assert response.status_code == 422
