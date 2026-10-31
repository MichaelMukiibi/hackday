import os
from dotenv import load_dotenv

import adaption
from adaption import Adaption

# Load ENV variables from .env file
load_dotenv()

# Adaptation API Client
client = Adaption(api_key=os.getenv("ADAPTION_API_KEY"))

def main():
    print(f"Adaption version: {adaption.__version__}")

if __name__ == "__main__":
    main()