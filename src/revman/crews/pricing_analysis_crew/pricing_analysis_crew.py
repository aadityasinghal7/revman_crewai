"""
Pricing Analysis Crew

This crew analyzes historical pricing data, forecasts next week's prices,
and identifies statistically significant price changes.
"""

import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from revman.tools import (
    HistoricalPriceAnalysisTool,
    PriceForecastingTool,
    AnomalyDetectionTool,
)


# Azure OpenAI LLM Configuration (using OpenAI-compatible endpoint)
def get_azure_llm(max_tokens: int = 4096) -> LLM:
    """Create Azure OpenAI LLM instance using OpenAI provider format.
    
    This uses the openai/ prefix which is natively supported by CrewAI.
    Azure OpenAI endpoint must be OpenAI-compatible.
    """
    azure_base = os.getenv("AZURE_API_BASE", "")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    
    # Format: openai/<deployment-name> with Azure base URL
    return LLM(
        model="openai/gpt-4o",  # deployment name in Azure
        api_key=os.getenv("AZURE_API_KEY"),
        base_url=f"{azure_base.rstrip('/')}/openai/deployments/gpt-4o?api-version={api_version}",
        max_tokens=max_tokens,
    )


@CrewBase
class PricingAnalysisCrew:

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def pricing_trend_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["pricing_trend_analyst_agent"],
            llm=get_azure_llm(),
            tools=[
                HistoricalPriceAnalysisTool().tool(),
                PriceForecastingTool().tool(),
                AnomalyDetectionTool().tool()
            ],
            verbose=True,
        )

    @task
    def analyze_historical_trends(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_historical_trends"],
        )

    @task
    def forecast_next_week_prices(self) -> Task:
        return Task(
            config=self.tasks_config["forecast_next_week_prices"],
        )

    @task
    def identify_notable_changes(self) -> Task:
        return Task(
            config=self.tasks_config["identify_notable_changes"],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
