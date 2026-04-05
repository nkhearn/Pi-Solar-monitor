import os
import google.generativeai as genai
import pi_solar_api_tool

# Configure the Gemini API key from environment variable
# export GOOGLE_API_KEY="your_api_key_here"
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Warning: GOOGLE_API_KEY environment variable not set.")
else:
    genai.configure(api_key=api_key)

# Map of tool names to actual functions in pi_solar_api_tool.py
TOOLS = {
    "get_available_metrics": pi_solar_api_tool.get_available_metrics,
    "get_latest_data": pi_solar_api_tool.get_latest_data,
    "get_metric_last_value": pi_solar_api_tool.get_metric_last_value,
    "get_metric_history": pi_solar_api_tool.get_metric_history,
    "get_metric_statistics": pi_solar_api_tool.get_metric_statistics,
    "get_metric_specific_stat": pi_solar_api_tool.get_metric_specific_stat,
    "list_virtual_metrics": pi_solar_api_tool.list_virtual_metrics,
    "get_system_history": pi_solar_api_tool.get_system_history,
}

def main():
    if not api_key:
        return

    # Initialize the model with the tool definitions
    # Note: Using the functions directly in the 'tools' list allows Gemini to call them.
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest',
        tools=list(TOOLS.values())
    )

    # Start a chat session
    chat = model.start_chat(enable_automatic_function_calling=True)

    # Example prompt to demonstrate tool discovery and usage
    prompt = "What is the current battery voltage and what was the average pv_power over the last hour?"

    print(f"User: {prompt}")
    response = chat.send_message(prompt)

    print(f"Gemini: {response.text}")

    # You can also manually handle function calls if preferred, but 'enable_automatic_function_calling=True'
    # handles the interaction loop automatically for simple use cases.

if __name__ == "__main__":
    main()
