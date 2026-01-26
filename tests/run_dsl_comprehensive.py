import asyncio
import sys
import os

# Aggiungiamo src al path per importare il framework
sys.path.append(os.path.join(os.getcwd(), 'src'))

from framework.service.language import parse_dsl_file, run_dsl_tests, DSLVisitor, dsl_functions

async def main():
    print("🚀 Avvio DSL Comprehensive Test Suite...\n")
    
    path = "tests/dsl_comprehensive_test.dsl"
    if not os.path.exists(path):
        print(f"❌ File {path} non trovato.")
        return

    with open(path, 'r') as f:
        content = f.read()

    try:
        # 1. Parsing
        print("🔍 Step 1: Parsing...")
        parsed_data = parse_dsl_file(content)
        
        # 2. Esecuzione
        print("🏃 Step 2: Esecuzione e Validazione...")
        visitor = DSLVisitor(dsl_functions)
        
        # Eseguiamo il file per popolare il contesto
        context = await visitor.run(parsed_data)
        
        # Eseguiamo la validazione formale via test_suite
        success = await run_dsl_tests(visitor, context)
        
        if success:
            print("\n✨ TUTTI I TEST COMPREHENSIVE SONO PASSATI!")
            sys.exit(0)
        else:
            print("\n❌ ALCUNI TEST COMPREHENSIVE SONO FALLITI.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
