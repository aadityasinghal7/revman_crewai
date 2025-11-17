"""
Pricing Analysis Crew

This crew analyzes historical pricing data, forecasts next week's prices,
and identifies statistically significant price changes.
"""

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from revman.tools import (
    HistoricalPriceAnalysisTool,
    PriceForecastingTool,
    AnomalyDetectionTool,
)


@CrewBase
class PricingAnalysisCrew:
    """Pricing Analysis Crew for trend analysis and forecasting"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def pricing_trend_analyst_agent(self) -> Agent:
        """
        Agent responsible for analyzing pricing trends, forecasting prices,
        and identifying anomalies.
        """
        return Agent(
            config=self.agents_config["pricing_trend_analyst_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            tools=[
                HistoricalPriceAnalysisTool().tool(),
                PriceForecastingTool().tool(),
                AnomalyDetectionTool().tool(),
            ],
            verbose=True,
        )

    @task
    def analyze_historical_trends(self) -> Task:
        """
        Task to analyze historical price data and calculate week-over-week changes.
        """
        return Task(
            config=self.tasks_config["analyze_historical_trends"],
        )

    @task
    def forecast_next_week_prices(self) -> Task:
        """
        Task to forecast next week's prices for all SKUs using trend analysis.
        """
        return Task(
            config=self.tasks_config["forecast_next_week_prices"],
        )

    @task
    def identify_notable_changes(self) -> Task:
        """
        Task to identify top 10 SKUs with statistically significant price changes.
        """
        return Task(
            config=self.tasks_config["identify_notable_changes"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Pricing Analysis Crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
