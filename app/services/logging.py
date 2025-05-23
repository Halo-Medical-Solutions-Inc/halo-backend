import logging
import os
from datetime import datetime

"""
Logging Service for the Halo Application.

This module provides a centralized logging service for the application.
It includes functionality for setting up and managing loggers for different components.

All logging operations are encapsulated in the setup_logger function,
with proper error handling and logging.
"""

def setup_logger():
    """
    Setup the logger for the database.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    directory = os.path.join(root, 'logs')
    os.makedirs(directory, exist_ok=True)
    
    log = logging.getLogger('database')
    log.setLevel(logging.ERROR)
    
    path = os.path.join(directory, f"errors_{datetime.now().strftime('%Y-%m-%d')}.log")
    handler = logging.FileHandler(path)
    handler.setLevel(logging.ERROR)
    
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    log.addHandler(handler)
    
    return log

logger = setup_logger()