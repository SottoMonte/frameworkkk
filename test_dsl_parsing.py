
import asyncio
from framework.service.language import parse_dsl_file, ConfigTransformer
from lark import Lark

dsl_content = """
{
    messenger.read(domain:'ciao'): messenger.post(message:"Hello World")|print;
    *,*,*,*,4,: "ciao cronos" | print;
}
"""

def test_parse():
    try:
        from framework.service.language import grammar
        parser = Lark(grammar, parser='earley')
        tree = parser.parse(dsl_content)
        print("Tree parsed successfully")
        result = ConfigTransformer().transform(tree)
        print("Result:", result)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_parse()
