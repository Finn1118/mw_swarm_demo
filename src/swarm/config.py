from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "SWARM_", "env_file": ".env", "env_file_encoding": "utf-8"}

    # API
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = True

    # OpenAI (for simulation LLM calls)
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    # Narrator model — flagship reasoning model with web search for grounded world simulation
    narrator_model: str = "gpt-5.4"
    narrator_reasoning_effort: str = "medium"

    # Thorsten 4 (for personality profiling)
    thorsten_api_key: str = ""

    # SEC EDGAR
    edgar_user_agent: str = "MillionWays Swarm research@example.com"

    # Simulation defaults
    sim_max_rounds: int = 10
    sim_temperature: float = 0.7


settings = Settings()
