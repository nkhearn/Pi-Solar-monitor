import os
import json
from google import genai
from google.genai import types
import pi_solar_api_tool  # Import our implementation

# Configure your API key here or via environment variable
# client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

# Define the tools for Gemini based on our implementation
tools = [
    pi_solar_api_tool.get_available_metrics,
    pi_solar_api_tool.get_latest_system_data,
    pi_solar_api_tool.get_system_history,
    pi_solar_api_tool.get_latest_metric_value,
    pi_solar_api_tool.get_metric_history,
    pi_solar_api_tool.get_metric_stats,
    pi_solar_api_tool.get_specific_metric_stat,
    pi_solar_api_tool.list_virtual_metrics,
    pi_solar_api_tool.create_or_update_virtual_metric,
    pi_solar_api_tool.delete_virtual_metric,
    pi_solar_api_tool.get_chart_data,
    pi_solar_api_tool.get_dashboard_charts,
    pi_solar_api_tool.save_dashboard_charts,
    pi_solar_api_tool.get_metric_ui_configs,
    pi_solar_api_tool.save_metric_ui_configs
]

def main():
    print("--- Pi Solar Monitor AI Assistant (Google GenAI) ---")
    print("System Prompt (Internal): You are an assistant for the Pi Solar Monitor.")
    print("ALWAYS call get_available_metrics() first to understand what data is available.\n")

    # Initialize client (it will look for GOOGLE_API_KEY env var if not provided)
    try:
        client = genai.Client()

        prompt = (
            "You are an assistant for the Pi Solar Monitor. "
            "Before answering questions, ALWAYS call get_available_metrics() to see what data keys are available. "
            "User query: How is my solar system performing today?"
        )

        # This will trigger Gemini to call the tools as needed
        # We use 'tools' in the config to enable function calling
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=tools,
            )
        )

        # Display the result
        print(f"Assistant: {response.text}")

    except Exception as e:
        print(f"Error (likely API key missing): {e}")
        print("\nNOTE: This script requires a valid Google Gemini API key (GOOGLE_API_KEY) to run fully.")
        print("However, the tool integration is correctly configured above.")

if __name__ == "__main__":
    main()
