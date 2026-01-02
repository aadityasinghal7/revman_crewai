"""
Excel Processor Crew

Parses and analyzes price change data from Excel files.
Uses SDK task chaining via context parameter for data flow between tasks.
"""

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

from revman.tools import (
    ExcelReaderTool,
    FormulaExcelGeneratorTool,
    DateExtractorTool,
    PriceCategorizationTool,
)
from revman.models.excel_processing import PriceCategorizationOutput


@CrewBase
class ExcelProcessorCrew:
    """Excel Processor Crew - Parses and analyzes price change data from Excel files"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def excel_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["excel_parser_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-20250514"),
            tools=[
                ExcelReaderTool(),
                FormulaExcelGeneratorTool(),
                DateExtractorTool()
            ],
            verbose=True,
        )

    @agent
    def data_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_analyst_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-20250514"),
            tools=[PriceCategorizationTool()],
            verbose=True,
        )

    @task
    def parse_excel_file(self) -> Task:
        """First task - parses the Excel file. Tool returns structured data."""
        return Task(
            config=self.tasks_config["parse_excel_file"],
        )

    @task
    def extract_effective_date(self) -> Task:
        """Second task - extracts date from filename."""
        return Task(
            config=self.tasks_config["extract_effective_date"],
            context=[self.parse_excel_file()],
        )

    @task
    def generate_formula_excel(self) -> Task:
        """Third task - generates formula Excel."""
        return Task(
            config=self.tasks_config["generate_formula_excel"],
            context=[self.parse_excel_file()],
        )

    @task
    def analyze_price_changes(self) -> Task:
        """Fourth task - categorizes price changes.

        Uses output_json with simplified flat model
        PriceCategorizationOutput uses simple string lists instead of complex nested structures.
        """
        return Task(
            config=self.tasks_config["analyze_price_changes"],
            context=[self.generate_formula_excel()],
            output_json=PriceCategorizationOutput,  # SDK-optimized flat schema
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Excel Processor crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,  
            process=Process.sequential,
            verbose=True,
        )
