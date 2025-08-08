import asyncio
import time
import logging
import zendriver as zd

SESSION_TTL = 20
SESSION_SWEEP_INTERVAL = 20

logger = logging.getLogger(__name__)


class _BrowserPool:
    """
    _BrowserPool manages a pool of browser sessions, each associated with a unique session ID (sid).
    
    Responsibilities:
        - Encapsulates the management of `zendriver.Browser` objects, exposing only the `zendriver.Tab` interface.
        - Provides asynchronous access to browser tabs via `get_tab`, reusing browsers for the same session ID or starting new ones as needed.
        - Tracks the last-used timestamp for each session and periodically sweeps/cleans up expired sessions based on a configurable TTL.
        - Ensures thread-safe access to the pool using an asyncio lock.
        - Offers a method to list current sessions and their last-used timestamps.
    
    Design Principles:
        - Hides direct browser management from consumers; only tabs are exposed.
    """
    

    # Design Principle: 
    #   1. Encapsulate away the zd.Browser object and just use the zd.Tab object
    def __init__(self):
        self._pool: dict[str, tuple[zd.Browser, float]] = {}
        self._lock = asyncio.Lock()

    async def get_tab(self, sid: str) -> zd.Tab:
        async with self._lock:
            if sid in self._pool:
                logger.info(f"sid: {sid} Reusing browser")
                browser, _ = self._pool[sid]
            else:
                logger.info(f"sid: {sid} Starting browser")
                browser = await zd.start(no_sandbox=True)
            # Refresh timestamp
            self._pool[sid] = (browser, time.time())
            return browser.main_tab
    
    async def sweep_expired_sessions(self) -> None:
        while True:
            # Sweep expired sessions every SESSION_SWEEP_INTERVAL seconds
            await asyncio.sleep(SESSION_SWEEP_INTERVAL)
            
            async with self._lock:
                # Convert to list to avoid modifying the dictionary while iterating
                for sid, (browser, last_used) in list(self._pool.items()):
                    # Delete expired sessions
                    if time.time() - last_used > SESSION_TTL:
                        logger.info(f"sid: {sid} Closing browser")
                        await browser.stop()
                        del self._pool[sid]
    
    def list_sessions(self) -> dict[str, float]:
        return {sid: ttl for sid, (_, ttl) in self._pool.items()}
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            for sid, (browser, _) in list(self._pool.items()):
                logger.info(f"sid: {sid} Destructor closing browser")
                await browser.stop()
            self._pool.clear()

    async def close(self):
        """
        Destructor-like method to close all browsers in the pool.
        """
        async with self._lock:
            for sid, (browser, _) in list(self._pool.items()):
                logger.info(f"sid: {sid} Destructor closing browser")
                await browser.stop()
            self._pool.clear()