import asyncio
import json
from framework.service.language import parse_dsl_file

dsl_content = """
{
    static_services : (
        {"path": "infrastructure/message/console.py"; "service": "message"; "adapter": "adapter"; "payload": "config";}
    );
    managers : (
        {"path": "framework/manager/messenger.py"; "service": "messenger";}
    );
}
"""

def debug_parsing():
    print("--- Testing DSL Parsing ---")
    try:
        result = parse_dsl_file(dsl_content)
        print("Parsed result:")
        print(json.dumps(result, indent=2, default=str))
        
        static = result.get('static_services')
        if static:
            print("\nStatic services first item keys:", list(static[0].keys()) if static and isinstance(static[0], dict) else "Not a dict or empty")
            
    except Exception as e:
        print(f"Error during parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_parsing()
