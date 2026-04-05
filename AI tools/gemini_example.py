import os
import json
import requests
from google import genai
from google.genai import types
import pi_solar_api_tool  # Import our implementation

# Map tool names to functions for automatic dispatch
available_tools = {
    "get_available_metrics": pi_solar_api_tool.get_available_metrics,
    "get_latest_system_data": pi_solar_api_tool.get_latest_system_data,
    "get_system_history": pi_solar_api_tool.get_system_history,
    "get_latest_metric_value": pi_solar_api_tool.get_latest_metric_value,
    "get_metric_history": pi_solar_api_tool.get_metric_history,
    "get_metric_stats": pi_solar_api_tool.get_metric_stats,
    "get_specific_metric_stat": pi_solar_api_tool.get_specific_metric_stat,
    "list_virtual_metrics": pi_solar_api_tool.list_virtual_metrics,
    "get_chart_data": pi_solar_api_tool.get_chart_data,
    "get_dashboard_charts": pi_solar_api_tool.get_dashboard_charts,
    "get_metric_ui_configs": pi_solar_api_tool.get_metric_ui_configs
}

def main():
    print("--- Pi Solar Monitor AI Assistant (Google GenAI) ---")
    print("System Prompt: You are an assistant for the Pi Solar Monitor.")
    print("ALWAYS call get_available_metrics() first to understand what data is available.\n")

    # Initialize client (it will look for GOOGLE_API_KEY env var if not provided)
    try:
        # Check if API is up
        try:
            requests.get(pi_solar_api_tool.BASE_URL + "/api/keys", timeout=2)
        except requests.exceptions.RequestException:
            print(f"WARNING: Pi Solar Monitor API is NOT running at {pi_solar_api_tool.BASE_URL}")
            print("Please start the API first (e.g., 'python3 main.py').\n")

        client = genai.Client()

        prompt = (
            "You are an assistant for the Pi Solar Monitor. "
            "Before answering questions, ALWAYS call get_available_metrics() to see what data keys are available. "
            "User query: How is my solar system performing today?"
        )

        # Start a chat with automatic function calling enabled.
        # This is the easiest and most functional way in the current SDK.
        chat = client.chats.create(
            model='gemini-2.0-flash',
            config=types.GenerateContentConfig(
                tools=list(available_tools.values()),
                system_instruction="You are a Pi Solar Monitor assistant. Always discovery metrics first.",
            )
        )

        # Gemini will automatically call the tools if they are in the 'tools' list
        # and the SDK's automatic dispatch is enabled (default in chat.create).
        response = chat.send_message(prompt)

        # Print the final generated text
        print(f"Assistant: {response.text}")

    except Exception as e:
        print(f"Error (likely API key missing): {e}")
        print("\nNOTE: This script requires a valid Google Gemini API key (GOOGLE_API_KEY) to run fully.")

if __name__ == "__main__":
    main()
