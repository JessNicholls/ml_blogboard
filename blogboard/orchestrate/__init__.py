# blogboard/orchestrate — IBM Watsonx Orchestrate integration package.
#
# This package contains the YAML specs that define the BlogBoard agents and
# tools for deployment to the IBM Watsonx Orchestrate platform.
#
# Layout
# ------
# tools/
#   tutorial_agent.yaml  — PythonTool wrapping tutorial_node
#   news_agent.yaml      — PythonTool wrapping news_node
#   validator_agent.yaml — PythonTool wrapping validator_node
#
# agents/
#   blogboard_orchestrator.yaml — Native agent that orchestrates all three tools
#
# Deployment (requires ORCHESTRATOR=wxorchestrate and credentials in .env)
# -------------------------------------------------------------------------
#   orchestrate env activate <your-environment>
#   orchestrate tools import python -f blogboard/orchestrate/tools/tutorial_agent.yaml
#   orchestrate tools import python -f blogboard/orchestrate/tools/news_agent.yaml
#   orchestrate tools import python -f blogboard/orchestrate/tools/validator_agent.yaml
#   orchestrate agents import -f blogboard/orchestrate/agents/blogboard_orchestrator.yaml
