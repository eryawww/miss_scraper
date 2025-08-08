from agno.playground import Playground
from miss_scraper.agents.serve import agent, lifespan

# Setup the Playground app
playground = Playground(
    agents=[agent],
    name="Miss Scraper",
    description="A playground for Miss Scraper",
    app_id="miss-scraper",
    monitoring=True,
)

# Initialize the Playground app with our lifespan logic
app = playground.get_app(lifespan=lifespan)


if __name__ == "__main__":
    playground.serve(app="miss_scraper.agents.playground:app", reload=True)