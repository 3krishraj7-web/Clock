import asyncio
import sys
sys.path.append('/app/backend')

from scheduler_manager import SchedulerManager

async def test_scheduler():
    try:
        sm = SchedulerManager()
        await sm.start()
        print('Scheduler started successfully')
        await sm.shutdown()
        print('Scheduler shutdown successfully')
        return True
    except Exception as e:
        print(f'Scheduler error: {e}')
        return False

if __name__ == "__main__":
    result = asyncio.run(test_scheduler())
    sys.exit(0 if result else 1)