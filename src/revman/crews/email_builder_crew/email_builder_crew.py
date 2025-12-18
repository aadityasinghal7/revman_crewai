import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task


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
