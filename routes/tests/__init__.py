"""Tests package initialization."""
from flask import Blueprint

# Create main tests blueprint
tests_bp = Blueprint("tests", __name__, url_prefix="/api/test")

# Import routes to register them
from . import general, tremor, drawing, speech
