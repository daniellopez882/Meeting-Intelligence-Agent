
import argparse
import sys
import os
from src.core.llm_client import LLMClient
from src.orchestrator.orchestrator import Orchestrator

def main():
    parser = argparse.ArgumentParser(description="Agentic AI Platform CLI")
    parser.add_argument("--request", type=str, required=True, help="User request/instruction (e.g., 'Analyze this meeting')")
    parser.add_argument("--file", type=str, help="Path to transcript file")
    parser.add_argument("--text", type=str, help="Direct text input")
    parser.add_argument("--provider", type=str, default="anthropic", choices=["anthropic", "openai"], help="LLM Provider")

    args = parser.parse_args()

    # Input validation
    content = ""
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found at {args.file}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.text:
        content = args.text
    else:
        print("Error: Must provide either --file or --text")
        sys.exit(1)

    try:
        # Initialize Client
        client = LLMClient(provider=args.provider)
        
        # Initialize Orchestrator
        orchestrator = Orchestrator(client)
        
        print(f"Processing request: {args.request}...")
        result = orchestrator.process_request(args.request, content)
        
        # Output result
        import json
        print(json.dumps(result, indent=2))
        
    except ValueError as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
