import yagmail
from app.services.logging import logger
import random

"""
Email Service for the Halo Application.

This module provides email functionality for sending verification codes
and password reset codes to users.
"""

class EmailService:
    """
    Email service class that handles sending emails for verification and password reset.
    """
    
    def __init__(self):
        """
        Initialize the email service with yagmail configuration.
        """
        try:
            self.yag = yagmail.SMTP('keshav@halohealth.app', 'tqxs jahf lose dmuc')
        except Exception as e:
            logger.error(f"Failed to initialize email service: {str(e)}")
            raise
    
    def generate_code(self) -> str:
        """
        Generate a 4-digit numeric verification code.
        
        Returns:
            str: A 4-digit numeric code as a string.
        """
        return str(random.randint(1000, 9999))
    
    def send_verification_email(self, email: str, code: str) -> bool:
        """
        Send email verification code to user.
        
        Args:
            email (str): The recipient's email address.
            code (str): The 4-digit verification code.
            
        Returns:
            bool: True if email was sent successfully, False otherwise.
        """
        try:
            subject = 'Email verification for Halo Scribe'
            contents = f"""
Your verification code is: {code}

This code will expire in 1 hour.

If you didn't request this verification, please ignore this email.
"""
            self.yag.send(
                to=email,
                subject=subject,
                contents=contents
            )
            logger.info(f"Verification email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, email: str, code: str) -> bool:
        """
        Send password reset code to user.
        
        Args:
            email (str): The recipient's email address.
            code (str): The 4-digit reset code.
            
        Returns:
            bool: True if email was sent successfully, False otherwise.
        """
        try:
            subject = 'Password reset for Halo Scribe'
            contents = f"""
Your password reset code is: {code}

This code will expire in 1 hour.

If you didn't request a password reset, please ignore this email.
"""
            self.yag.send(
                to=email,
                subject=subject,
                contents=contents
            )
            logger.info(f"Password reset email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False

email_service = EmailService() 