#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/teq-admin/Downloads')

from lambda_function_batch_push import lambda_handler

# Test the lambda function
if __name__ == "__main__":
    # Test event (simulating AWS Lambda or direct call)
    event = {}
    context = {}

    print("=" * 60)
    print("Testing lambda_function.py")
    print("=" * 60)

    result = lambda_handler(event, context)

    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(f"Status Code: {result['statusCode']}")
    print(f"Body: {result['body']}")
