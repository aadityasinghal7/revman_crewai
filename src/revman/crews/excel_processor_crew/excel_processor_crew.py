from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


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
            verbose=True,
        )

    @agent
    def data_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_analyst_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            verbose=False,
        )

    @agent
    def data_validator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["data_validator_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            verbose=True,
        )

    @task
    def parse_excel_file(self) -> Task:
        return Task(
            config=self.tasks_config["parse_excel_file"],
        )

    @task
    def analyze_price_changes(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_price_changes"],
        )

    @task
    def validate_data_quality(self) -> Task:
        return Task(
            config=self.tasks_config["validate_data_quality"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Excel Processor crew"""
        return Crew(
            agents=self.agents,  # Automatically includes all @agent decorated methods
            tasks=self.tasks,  # Automatically includes all @task decorated methods
            process=Process.sequential,
            verbose=False,
        )
