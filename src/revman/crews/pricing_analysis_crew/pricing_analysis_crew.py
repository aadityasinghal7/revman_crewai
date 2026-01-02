"""
Pricing Analysis Crew

This crew analyzes historical pricing data, forecasts next week's prices,
and identifies statistically significant price changes.

Uses SDK task chaining via context parameter for data flow between tasks.
"""

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from revman.tools import (
    HistoricalPriceAnalysisTool,
    PriceForecastingTool,
    AnomalyDetectionTool,
)
from revman.models.pricing import PricingAnalysisOutput


@CrewBase
class PricingAnalysisCrew:

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def pricing_trend_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["pricing_trend_analyst_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-20250514"),
            tools=[
                HistoricalPriceAnalysisTool(),
                PriceForecastingTool(),
                AnomalyDetectionTool()
            ],
            verbose=True,
        )

    @task
    def analyze_historical_trends(self) -> Task:
        """First task - analyzes historical price data.
        
        Note: No output_pydantic - tool returns structured data directly.
        LLMs struggle to reproduce complex nested JSON like Dict[str, SKUAnalysis].
        """
        return Task(
            config=self.tasks_config["analyze_historical_trends"],
        )

    @task
    def forecast_next_week_prices(self) -> Task:
        """Second task - uses historical analysis via context parameter.
        
        Note: No output_pydantic - tool returns structured data directly.
        """
        return Task(
            config=self.tasks_config["forecast_next_week_prices"],
            context=[self.analyze_historical_trends()],
        )

    @task
    def identify_notable_changes(self) -> Task:
        """Third task - uses forecast data via context parameter.

        Uses output_json with simplified model for better LLM reliability.
        PricingAnalysisOutput uses List[Dict] instead of nested Pydantic models.
        CrewAI automatically instructs LLM to output valid JSON matching schema.
        """
        return Task(
            config=self.tasks_config["identify_notable_changes"],
            context=[self.forecast_next_week_prices()],
            output_json=PricingAnalysisOutput,  # SDK-optimized flat schema
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
