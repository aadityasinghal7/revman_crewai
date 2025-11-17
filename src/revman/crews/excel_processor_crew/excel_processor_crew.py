from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from revman.tools import ExcelReaderTool, DataCleanerTool, PriceCalculatorTool, FormulaExcelGeneratorTool, DateExtractorTool, PriceCategorizationTool


@CrewBase
class ExcelProcessorCrew:
    """Excel Processor Crew - Parses and analyzes price change data from Excel files"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def excel_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["excel_parser_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            tools=[ExcelReaderTool().tool(), DataCleanerTool().tool(), FormulaExcelGeneratorTool().tool(), DateExtractorTool().tool()],
            verbose=True,  # Enabled for debugging - shows agent reasoning
        )

    @agent
    def data_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_analyst_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            tools=[PriceCalculatorTool().tool(), PriceCategorizationTool().tool()],
            verbose=True,  # Enabled for debugging - shows agent reasoning
        )

    @task
    def parse_excel_file(self) -> Task:
        return Task(
            config=self.tasks_config["parse_excel_file"],
        )

    @task
    def extract_effective_date(self) -> Task:
        return Task(
            config=self.tasks_config["extract_effective_date"],
        )

    @task
    def generate_formula_excel(self) -> Task:
        return Task(
            config=self.tasks_config["generate_formula_excel"],
        )

    @task
    def analyze_price_changes(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_price_changes"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Excel Processor crew"""
        return Crew(
            agents=self.agents,  # Automatically includes all @agent decorated methods
            tasks=self.tasks,  # Automatically includes all @task decorated methods
            process=Process.sequential,
            verbose=True,  # Enabled for debugging
        )
