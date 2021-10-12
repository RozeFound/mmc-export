import sys
import asyncio
from .main import main

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
loop = asyncio.get_event_loop()
loop.run_until_complete(main())