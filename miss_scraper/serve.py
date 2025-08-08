from fastapi import FastAPI
from miss_scraper.mcp.serve import mcp_app
from miss_scraper.agents.serve import agent_app
from fastapi.middleware.cors import CORSMiddleware
from miss_scraper.mcp.tools.browser import router as browser_router
import dotenv
import logging
from contextlib import asynccontextmanager

dotenv.load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    filename=f"tmp/miss_scraper.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("miss_scraper").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # start & stop the child’s lifespan “manually”
    async with agent_app.router.lifespan_context(agent_app):
        yield

app = FastAPI(title="Miss Scraper", lifespan=lifespan)

######
# include agent routes on /agents
app.mount('/agents', agent_app.router)

# include mcp routes on /mcp
app.mount('/mcp', mcp_app.router)

# include tools debugging routes
app.include_router(browser_router, prefix='/tools/browser')
######



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
def read_root():
    return {'message': 'Hello, World!'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)