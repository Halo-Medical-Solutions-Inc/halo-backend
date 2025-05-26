from datetime import datetime

"""
Prompts Service for the Halo Application.

This module provides a service for generating prompts for the AI medical scribe.
It includes functionality for generating prompts for the AI medical scribe to follow when generating or modifying a clinical note.
"""

def get_instructions(prompt, transcript, additional_context, template_instructions, user_specialty, user_name):
    """
    Generate instructions for the AI medical scribe.

    This function processes a prompt template by replacing variables with their corresponding values.

    Args:
        prompt (str): The prompt template with variables to be replaced.
        transcript (str): The transcript of the audio recording.
        additional_context (str): Additional context or information about the patient.
        template_instructions (str): Instructions for the AI medical scribe.
        user_specialty (str): The specialty of the user.

    Returns:
        str: The processed prompt with variables replaced.
    """
    processed_prompt = prompt
    replacements = {
        "{{today_date}}": datetime.utcnow().strftime("%Y-%m-%d"),
        "{{transcript}}": transcript,
        "{{additional_context}}": additional_context,
        "{{template_instructions}}": template_instructions,
        "{{user_specialty}}": user_specialty,
        "{{user_name}}": user_name
    }
    for placeholder, value in replacements.items():
        try:
            processed_prompt = processed_prompt.replace(placeholder, value)
        except:
            pass
    if processed_prompt == "":
        processed_prompt = f"Write a medical note based on the following transcript: {transcript}"
    return processed_prompt

def get_template_instructions(prompt, template_instructions):
    """
    Generate instructions for the AI medical scribe.

    This function processes a prompt template by replacing template_instructions variable.

    Args:
        prompt (str): The prompt template with variables to be replaced.
        template_instructions (str): Instructions for the AI medical scribe.

    Returns:
        str: The processed prompt with variables replaced.
    """
    processed_prompt = prompt
    replacements = {
        "{{template_instructions}}": template_instructions
    }
    for placeholder, value in replacements.items():
        try:
            processed_prompt = processed_prompt.replace(placeholder, value)
        except:
            pass
    if processed_prompt == "":
        processed_prompt = f"Create a template based on the following instructions: {template_instructions}"
    return processed_prompt