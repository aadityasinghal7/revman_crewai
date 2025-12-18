import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


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
class EmailBuilderCrew:
    """Email Builder Crew - Generates plain text email from price change data in template format"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def email_content_writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["email_content_writer_agent"],
            llm=get_azure_llm(max_tokens=8000),
            verbose=True,  # Enabled for debugging - shows agent reasoning
        )
    

    @task
    def write_highlights_content(self) -> Task:
        return Task(
            config=self.tasks_config["write_highlights_content"],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Email Builder crew"""
        return Crew(
            agents=self.agents,  # Automatically includes all @agent decorated methods
            tasks=self.tasks,  # Automatically includes all @task decorated methods
            process=Process.sequential,
            verbose=True,  # Enabled for debugging
        )
