"""
Email Builder Crew

Generates plain text email from price change data in template format.
Uses SDK output_file parameter to automatically save email content.
"""

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task


@CrewBase
class EmailBuilderCrew:
    """Email Builder Crew - Generates plain text email from price change data in template format"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def email_content_writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["email_content_writer_agent"],
            llm=LLM(model="anthropic/claude-sonnet-4-20250514", max_tokens=8000),
            verbose=True,
        )
    
    @task
    def write_highlights_content(self) -> Task:
        """Generates email content in template format."""
        return Task(
            config=self.tasks_config["write_highlights_content"],
            # Note: output_file can be set dynamically via kickoff inputs
            # or configured here with a static path
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Email Builder crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
