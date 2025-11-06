from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


@CrewBase
class EmailBuilderCrew:
    """Email Builder Crew - Generates formatted HTML email from price change data"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def email_content_writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["email_content_writer_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            verbose=True,
        )

    @agent
    def html_email_formatter_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["html_email_formatter_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-5-20250929"),
            verbose=True,
        )

    @task
    def write_highlights_content(self) -> Task:
        return Task(
            config=self.tasks_config["write_highlights_content"],
        )

    @task
    def format_as_html_email(self) -> Task:
        return Task(
            config=self.tasks_config["format_as_html_email"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Email Builder crew"""
        return Crew(
            agents=self.agents,  # Automatically includes all @agent decorated methods
            tasks=self.tasks,  # Automatically includes all @task decorated methods
            process=Process.sequential,
            verbose=False,
        )
