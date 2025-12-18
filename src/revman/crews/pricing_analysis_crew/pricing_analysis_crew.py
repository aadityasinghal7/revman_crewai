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
# Uses CrewAI LLM Connection: SupplyChainAnalytics-GPT-TEST-EastUS2
# Available models: azure/gpt-4.1, azure/gpt-4.1-mini, azure/gpt-5

def get_azure_llm(max_tokens: int = 4096) -> LLM:
    """Create Azure OpenAI LLM instance via CrewAI LLM Connection."""
    return LLM(
        model="azure/gpt-4.1",
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
