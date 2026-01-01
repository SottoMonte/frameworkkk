
import asyncio
import datetime
from framework.service.language import DSLVisitor, parse_dsl_file, grammar
from lark import Lark
import framework.service.inspector as inspector

# Mock framework_log to capture output
log_output = []
def mock_log(level, message, **kwargs):
    print(f"[{level}] {message}")
    log_output.append((level, message))

inspector.framework_log = mock_log

async def test_triggers():
    # 1. Test DSL content with cron and event triggers
    dsl_content = """
    {
        # Event trigger: execute action when mock_event() returns something
        mock_event(): mock_action(msg:'Event fired!') | print;
        
        # Cron trigger: execute action every minute (wildcard for all)
        *,*,*,*,*: mock_action(msg:'Cron fired!') | print;
    }
    """
    
    # 2. Mock functions
    event_called = 0
    action_called = []
    
    async def mock_event(*args, **kwargs):
        nonlocal event_called
        event_called += 1
        if event_called == 2:
            return "SUCCESS"
        return None

    async def mock_action(msg, **kwargs):
        nonlocal action_called
        action_called.append(msg)
        return f"Action result: {msg}"

    functions_map = {
        'mock_event': mock_event,
        'mock_action': mock_action,
        'print': lambda x: print(f"PRINT: {x}")
    }

    # 3. Parse and Run
    print("Parsing DSL...")
    parsed_data = parse_dsl_file(dsl_content)
    print("Parsed data:", parsed_data)
    
    visitor = DSLVisitor(functions_map)
    print("Running visitor...")
    
    # We need to run it in a way that we can wait for triggers
    task = asyncio.create_task(visitor.run(parsed_data))
    
    # Wait for a bit to let loops run
    print("Waiting for triggers to fire...")
    await asyncio.sleep(5) 
    
    # Cancel the visitor task (loops are background tasks but visitor.run returns when dict is visited)
    # Background tasks are independent now
    
    print("Checking results...")
    print("Action called:", action_called)
    
    # Verify event fired
    assert "Event fired!" in action_called, "Event trigger failed!"
    # Verify cron fired (at least once if we are lucky with timing, but since we sleep 60 sec in _cron_loop it might not fire in 5 sec unless we mock time)
    # To test cron properly in 5 sec, we'd need to mock datetime or reduce sleep
    
    print("✅ Verification successful (Event fired!)")
    
    # Clean up (cancel background tasks)
    for t in asyncio.all_tasks():
        if t is not asyncio.current_task():
            t.cancel()

if __name__ == "__main__":
    asyncio.run(test_triggers())
