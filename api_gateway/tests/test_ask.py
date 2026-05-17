def test_ask_happy_path(client, mock_agent):
    mock_agent.return_value = "Revenue is €1.2M this month."
    response = client.post("/ask", json={"question": "What is total revenue?"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Revenue is €1.2M this month."
    assert data["question"] == "What is total revenue?"


def test_ask_agent_error_returns_502(client, mock_agent):
    mock_agent.side_effect = Exception("Databricks unreachable")
    response = client.post("/ask", json={"question": "What is total revenue?"})
    assert response.status_code == 502


def test_ask_missing_question_returns_422(client):
    response = client.post("/ask", json={})
    assert response.status_code == 422
