import dotenv
dotenv.load_dotenv()

import logging

from agno.utils.log import agent_logger, team_logger, workflow_logger  
  
# Get the existing loggers and add your file handler  
file_handler = logging.FileHandler("tmp/miss_scraper_agents.log")  
file_handler.setLevel(logging.DEBUG)  
  
# Use a simpler formatter to avoid string formatting issues  
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')  
file_handler.setFormatter(formatter)  
  
# Add to existing loggers  
agent_logger.addHandler(file_handler)  
team_logger.addHandler(file_handler)  
workflow_logger.addHandler(file_handler)

from agno.playground import Playground
from miss_scraper.agents.repository import browser_agent, lifespan

# Setup the Playground app
playground = Playground(
    agents=[browser_agent],
    name="Miss Scraper",
    description="A playground for Miss Scraper",
    app_id="miss-scraper",
    monitoring=True,
)

# Initialize the Playground app with our lifespan logic
app = playground.get_app(lifespan=lifespan)


if __name__ == "__main__":
    playground.serve(app="miss_scraper.agents.playground:app", reload=True)