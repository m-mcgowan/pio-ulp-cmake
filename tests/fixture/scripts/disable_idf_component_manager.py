"""
Pre-build script to disable the ESP-IDF Component Manager.

The IDF Component Manager pulls in managed components (esp_insights,
esp_rainmaker, etc.) that are not needed for ULP testing and cause
build failures with target_add_binary_data.
"""

Import("env")
import os

os.environ["IDF_COMPONENT_MANAGER"] = "0"
