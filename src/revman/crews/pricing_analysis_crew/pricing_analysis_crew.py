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


# Azure OpenAI LLM Configuration
# Explicitly pass credentials from environment variables

def get_azure_llm(max_tokens: int = 4096) -> LLM:
    """Create Azure OpenAI LLM instance with explicit credentials."""
    return LLM(
        model="azure/gpt-4o",
        api_key=os.environ.get("AZURE_API_KEY"),
        endpoint=os.environ.get("AZURE_ENDPOINT") or os.environ.get("AZURE_API_BASE"),
        api_version=os.environ.get("AZURE_API_VERSION", "2024-06-01"),
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
