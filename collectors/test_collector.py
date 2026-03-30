#!/usr/bin/env python3
import json
import random

def main():
    data = {
        "voltage": 230.5,
        "current": 10.2,
        "power": 2351.1,
        "temperature": 25.4,
        "humidity": 45.2
    }
    print(json.dumps(data))

if __name__ == "__main__":
    main()
