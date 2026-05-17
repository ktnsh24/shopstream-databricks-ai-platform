def test_metrics_happy_path(client, mock_agent):
    mock_agent.return_value = "Total revenue: €1.2M, Orders: 4,500, AOV: €266."
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.json()["answer"] == "Total revenue: €1.2M, Orders: 4,500, AOV: €266."


def test_metrics_agent_error_returns_502(client, mock_agent):
    mock_agent.side_effect = Exception("timeout")
    response = client.get("/metrics")
    assert response.status_code == 502
