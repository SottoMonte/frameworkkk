import asyncio
import sys
import os

# Aggiungi src al PYTHONPATH
sys.path.append(os.path.abspath("src"))

from framework.service.language import DSLVisitor, grammar, ConfigTransformer
from lark import Lark
import framework.service.flow as flow

async def test_dsl():
    path = "showcase.dsl"
    with open(path, "r") as f:
        content = f.read()
    
    parser = Lark(grammar)
    tree = parser.parse(content)
    transformer = ConfigTransformer()
    dsl_dict = transformer.transform(tree)
    
    from framework.service.language import dsl_functions
    visitor = DSLVisitor(functions_map=dsl_functions)
    
    print(f"Executing {path}...")
    result = await visitor.run(dsl_dict)
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(test_dsl())
