import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task

from revman.tools import ExcelReaderTool, DataCleanerTool, PriceCalculatorTool, FormulaExcelGeneratorTool, DateExtractorTool, PriceCategorizationTool

# Azure OpenAI LLM Configuration
# Uses OpenAI-compatible endpoint with Azure OpenAI

def get_azure_llm(max_tokens: int = 4096) -> LLM:
    """Create Azure OpenAI LLM instance using OpenAI-compatible format."""
    return LLM(
        model="openai/gpt-4.1",
        api_key=os.getenv("AZURE_API_KEY"),
        base_url=os.getenv("AZURE_API_BASE"),
        max_tokens=max_tokens,
    )


@CrewBase
class ExcelProcessorCrew:
    """Excel Processor Crew - Parses and analyzes price change data from Excel files"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def excel_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["excel_parser_agent"],
            llm=get_azure_llm(),
            tools=[ExcelReaderTool().tool(), DataCleanerTool().tool(), FormulaExcelGeneratorTool().tool(), DateExtractorTool().tool()],
            verbose=True,  
        )

    @agent
    def data_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_analyst_agent"],
            llm=get_azure_llm(),
            tools=[PriceCalculatorTool().tool(), PriceCategorizationTool().tool()],
            verbose=True,  
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
            agents=self.agents,
            tasks=self.tasks,  
            process=Process.sequential,
            verbose=True,
        )
