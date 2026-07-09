# blogboard/orchestrate — IBM Watsonx Orchestrate integration package.
#
# This package contains the Python tool definitions and the native agent YAML
# for deployment to the IBM Watsonx Orchestrate platform via the ADK CLI.
#
# Layout
# ------
# tools/
#   tutorial_agent.py  — @tool wrapping tutorial_node
#   news_agent.py      — @tool wrapping news_node
#   validator_agent.py — @tool wrapping validator_node
#
# agents/
#   blogboard_orchestrator.yaml — Native agent that orchestrates all three tools
#
# Deployment (requires ibm-watsonx-orchestrate installed and credentials configured)
# ----------------------------------------------------------------------------------
#   # 1. Activate your environment (local Developer Edition or cloud):
#   orchestrate env activate <your-environment>
#
#   # 2. Import the Python tools:
#   orchestrate tools import python -f blogboard/orchestrate/tools/tutorial_agent.py
#   orchestrate tools import python -f blogboard/orchestrate/tools/news_agent.py
#   orchestrate tools import python -f blogboard/orchestrate/tools/validator_agent.py
#
#   # 3. Import the orchestrator agent:
#   orchestrate agents import -f blogboard/orchestrate/agents/blogboard_orchestrator.yaml
#
#   # 4. Verify:
#   orchestrate tools list
#   orchestrate agents list
#
#   # 5. Chat-test (dry run):
#   orchestrate chat -a blogboard_orchestrator
