"""
Application configuration.

All sensitive credentials should be set via environment variables.
See .env.example for the full list of configurable settings.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Path configuration
CONTROLLERS_PATH = "bots/conf/controllers"
CONTROLLERS_MODULE = "bots.controllers"
PASSWORD_VERIFICATION_PATH = "bots/credentials/master_account/.password_verification"

# Hummingbot configuration encryption password
CONFIG_PASSWORD = os.getenv("CONFIG_PASSWORD", "changeme")

# MQTT broker settings (EMQX)
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))
BROKER_USERNAME = os.getenv("BROKER_USERNAME", "admin")
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD", "public")

# Trading configuration
BANNED_TOKENS = os.getenv("BANNED_TOKENS", "NAV,ARS,ETHW,ETHF").split(",")