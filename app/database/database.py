from app.config import settings
from app.services.utils import decrypt, encrypt, hash_password
from bson import ObjectId
from datetime import datetime, timedelta
from pymongo import MongoClient
from app.services.logging import logger
import json

"""
MongoDB Database Handler for the Halo Application.

This module provides a centralized database access layer for all MongoDB operations.
It includes functionality for managing users, sessions, templates, and visits.

Key features:
- Encryption/decryption of sensitive data
- Session management
- User authentication and management
- Template management
- Visit tracking and statistics

All database operations are encapsulated in the database class,
with proper error handling and logging.
"""

class database:
    """
    Main database class that handles all interactions with MongoDB.
    Provides methods for CRUD operations on users, sessions, templates, and visits.
    """
    def __init__(self):
        """
        Initialize the database connection and set up collection references.
        Establishes connection to MongoDB using the URL from settings.
        Sets up references to various collections used in the application.
        
        Raises:
            Exception: If there's an error connecting to the database.
        """
        try:
            self.client = MongoClient(settings.MONGODB_URL)
            self.database = self.client['database']
            self.sessions = self.database['sessions']
            self.users = self.database['users']
            self.templates = self.database['templates']
            self.visits = self.database['visits']
            self.admins = self.database['admins']
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise

    def decrypt_session(self, session):
        """
        Decrypt and format a session document from the database.
        
        Args:
            session (dict): The encrypted session document from the database.
            
        Returns:
            dict: The decrypted session document with formatted fields, or None if error occurs.
            
        Note:
            Converts ObjectIds to strings and decrypts sensitive fields.
        """
        try:
            session_copy = session.copy()
            session_copy['session_id'] = str(session_copy['_id'])
            session_copy['user_id'] = str(session_copy['user_id'])
            session_copy['expiration_date'] = str(session_copy['expiration_date'])
            del session_copy['_id']
            return session_copy
        except Exception as e:
            logger.error(f"decrypt_session error for session_id {session.get('_id', 'unknown')}: {str(e)}")
            return None

    def create_session(self, user_id):
        """
        Create a new session for a user.
        
        Args:
            user_id (str): The ID of the user to create a session for.
            
        Returns:
            dict: The newly created session document, or None if creation failed.
            
        Note:
            Session expiration is set to 1 minute from creation.
        """
        try:
            session = {'user_id': user_id, 'expiration_date': datetime.utcnow() + timedelta(days=1)}
            self.sessions.insert_one(session)
            return self.decrypt_session(session)
        except Exception as e:
            logger.error(f"create_session error for user_id {user_id}: {str(e)}")
            return None

    def delete_session(self, session_id):
        """
        Delete a session from the database.
        
        Args:
            session_id (str): The ID of the session to delete.
            
        Note:
            This method does not return a value, and logs any errors.
        """
        try:
            self.sessions.delete_one({'_id': ObjectId(session_id)})
        except Exception as e:
            logger.error(f"delete_session error for session_id {session_id}: {str(e)}")

    def get_session(self, session_id):
        """
        Retrieve a session by its ID.
        
        Args:
            session_id (str): The ID of the session to retrieve.
            
        Returns:
            dict: The session document with formatted fields, or None if not found or error occurs.
        """
        try:
            session = self.sessions.find_one({'_id': ObjectId(session_id)})
            return self.decrypt_session(session)
        except Exception as e:
            logger.error(f"get_session error for session_id {session_id}: {str(e)}")
            return None

    def is_session_valid(self, session_id):
        """
        Check if a session is valid (exists and not expired).
        
        Args:
            session_id (str): The ID of the session to validate.
            
        Returns:
            str: The user_id associated with the session if valid, None otherwise.
        """
        try:
            session = self.get_session(session_id)
            if session:
                if datetime.fromisoformat(session['expiration_date'].replace('Z', '+00:00')) > datetime.utcnow():
                    return session['user_id']
            return None
        except Exception as e:
            logger.error(f"is_session_valid error for session_id {session_id}: {str(e)}")
            return None

    def decrypt_user(self, user):
        """
        Decrypt and format a user document from the database.
        
        Args:
            user (dict): The encrypted user document from the database.
            
        Returns:
            dict: The decrypted user document with formatted fields, or None if error occurs.
            
        Note:
            Converts ObjectIds to strings and decrypts sensitive fields.
            Only works with the new database format.
        """
        try:
            user_copy = user.copy()
            user_copy['user_id'] = str(user_copy['_id'])
            user_copy['visit_ids'] = [str(visit_id) for visit_id in user_copy['visit_ids']]
            user_copy['template_ids'] = [str(template_id) for template_id in user_copy['template_ids']]
            user_copy['name'] = decrypt(user_copy['encrypt_name'])
            user_copy['email'] = decrypt(user_copy['encrypt_email'])
            user_copy['created_at'] = str(user_copy['created_at'])
            user_copy['modified_at'] = str(user_copy['modified_at'])
            subscription = user_copy.get('subscription', {})
            if subscription.get('free_trial_expiration_date'):
                subscription['free_trial_expiration_date'] = str(subscription['free_trial_expiration_date'])
            user_copy['subscription'] = subscription
            miscellaneous = user_copy.get('miscellaneous', {})
            if miscellaneous.get('verification_expires_at'):
                miscellaneous['verification_expires_at'] = str(miscellaneous['verification_expires_at'])
            if miscellaneous.get('reset_expires_at'):
                miscellaneous['reset_expires_at'] = str(miscellaneous['reset_expires_at'])
            user_copy['miscellaneous'] = miscellaneous
            if 'emr_integration' in user_copy and user_copy['emr_integration']:
                emr_integration = user_copy['emr_integration']
                if 'encrypt_credentials' in emr_integration:
                    decrypted_credentials = decrypt(emr_integration['encrypt_credentials'])
                    emr_integration['credentials'] = json.loads(decrypted_credentials) if decrypted_credentials else {}
                    del emr_integration['encrypt_credentials']
                user_copy['emr_integration'] = emr_integration
            del user_copy['_id']
            del user_copy['encrypt_name']
            del user_copy['encrypt_email']
            del user_copy['hash_password']
            return user_copy
        except Exception as e:
            logger.error(f"decrypt_user error for user_id {user.get('_id', 'unknown')}: {str(e)}")
            return None
    
    def create_user(self, name, email, password, custom=False):
        """
        Create a new user in the database.
        
        Args:
            name (str): The user's name.
            email (str): The user's email address.
            password (str): The user's password.
            custom (bool): Whether the user is a custom user.
        Returns:
            dict: The newly created user document with decrypted fields, or None if creation failed.
            
        Note:
            Checks for existing users with the same email before creation.
            Automatically assigns default templates to new users.
        """
        try:
            encrypted_email = encrypt(email)
            all_users = list(self.users.find())
            for user in all_users:
                decrypted_email = decrypt(user['encrypt_email'])
                if decrypted_email == email:
                    return None
            default_templates = list(self.templates.find({'status': 'DEFAULT'}))
            default_template_ids = [template['_id'] for template in default_templates]
            default_template_id = str(default_templates[-1]['_id']) if default_templates else ''
            user = {
                'created_at': datetime.utcnow(),
                'modified_at': datetime.utcnow(),
                'status': 'UNVERIFIED' if not custom else 'ACTIVE',
                'encrypt_name': encrypt(name),
                'encrypt_email': encrypted_email,
                'hash_password': hash_password(password),
                'user_specialty': '',
                'default_template_id': default_template_id,
                'default_language': 'en',
                'template_ids': default_template_ids,
                'visit_ids': [],
                'daily_statistics': {},
                'emr_integration': {},
                'subscription': {
                    'plan': 'NO_PLAN' if not custom else 'CUSTOM',
                    'free_trial_used': False,
                    'free_trial_expiration_date': None,
                    'stripe_customer_id': None,
                    'stripe_subscription_id': None
                },
                'miscellaneous': {
                    'verification_code': None,
                    'verification_expires_at': None,
                    'reset_code': None,
                    'reset_expires_at': None
                }
            }
            self.users.insert_one(user)
            return self.decrypt_user(user)
        except Exception as e:
            logger.error(f"create_user error for email {email}: {str(e)}")
            return None
        
    def update_user(self, user_id, name=None, email=None, password=None, user_specialty=None, default_template_id=None, default_language=None, template_ids=None, visit_ids=None, emr_integration=None):
        """
        Update a user's information in the database.
        
        Args:
            user_id (str): The ID of the user to update.
            name (str, optional): The user's new name.
            email (str, optional): The user's new email address.
            password (str, optional): The user's new password.
            user_specialty (str, optional): The user's specialty.
            default_template_id (str, optional): The user's default template ID.
            default_language (str, optional): The user's default language.
            template_ids (list, optional): List of template IDs associated with the user.
            visit_ids (list, optional): List of visit IDs associated with the user.
            emr_integration (dict, optional): EMR integration configuration with credentials.
            
        Returns:
            dict: The updated user document with decrypted fields, or None if update failed.
        """
        try:
            update_fields = {}
            if name is not None:
                update_fields['encrypt_name'] = encrypt(name)
            if email is not None:
                update_fields['encrypt_email'] = encrypt(email)
            if password is not None:
                update_fields['hash_password'] = hash_password(password)
            if default_template_id is not None:
                update_fields['default_template_id'] = default_template_id
            if default_language is not None:
                update_fields['default_language'] = default_language
            if user_specialty is not None:
                update_fields['user_specialty'] = user_specialty
            if template_ids is not None:
                update_fields['template_ids'] = template_ids
            if visit_ids is not None:
                update_fields['visit_ids'] = visit_ids
            if emr_integration is not None:
                update_fields['emr_integration'] = emr_integration
            if update_fields:
                update_fields['modified_at'] = datetime.utcnow()
                self.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            user = self.users.find_one({'_id': ObjectId(user_id)})
            return self.decrypt_user(user)
        except Exception as e:
            logger.error(f"update_user error for user_id {user_id}: {str(e)}")
            return None
    
    def delete_user(self, user_id):
        """
        Delete a user from the database.
        
        Args:
            user_id (str): The ID of the user to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            self.users.delete_one({'_id': ObjectId(user_id)})
            return True
        except Exception as e:
            logger.error(f"delete_user error for user_id {user_id}: {str(e)}")
            return False
    
    def get_user(self, user_id):
        """
        Retrieve a user by their ID.
        
        Args:
            user_id (str): The ID of the user to retrieve.
            
        Returns:
            dict: The user document with decrypted fields, or None if not found or error occurs.
        """
        try:
            user = self.users.find_one({'_id': ObjectId(user_id)})
            return self.decrypt_user(user)
        except Exception as e:
            logger.error(f"get_user error for user_id {user_id}: {str(e)}")
            return None
    
    def get_user_by_email(self, email):
        """
        Retrieve a user by their email address.
        
        Args:
            email (str): The email address to search for.
            
        Returns:
            dict: The user document with decrypted fields, or None if not found or error occurs.
        """
        try:
            all_users = list(self.users.find())
            for user in all_users:
                decrypted_email = decrypt(user['encrypt_email'])
                if decrypted_email == email:
                    return self.decrypt_user(user)
            return None
        except Exception as e:
            logger.error(f"get_user_by_email error for email {email}: {str(e)}")
            return None
    
    def verify_user(self, email, password):
        """
        Verify a user's login credentials.
        
        Args:
            email (str): The user's email address.
            password (str): The user's password.
            
        Returns:
            dict: The user document with decrypted fields if credentials are valid, None otherwise.
        """
        try:
            hashed_password = hash_password(password)
            all_users = list(self.users.find())
            for user in all_users:
                decrypted_email = decrypt(user['encrypt_email'])
                if decrypted_email == email and user['hash_password'] == hashed_password:
                    return self.decrypt_user(user)
            return None
        except Exception as e:
            logger.error(f"verify_user error for email {email}: {str(e)}")
            return None
    
    def get_user_templates(self, user_id):
        """
        Retrieve all templates associated with a user.
        
        Args:
            user_id (str): The ID of the user.
            
        Returns:
            list: A list of template documents with decrypted fields, or empty list if error occurs.
        """
        try:
            user = self.get_user(user_id)
            template_ids = [ObjectId(tid) for tid in user['template_ids']]
            templates = list(self.templates.find({'_id': {'$in': template_ids}}))
            return [self.decrypt_template(template) for template in templates]
        except Exception as e:
            logger.error(f"get_user_templates error for user_id {user_id}: {str(e)}")
            return []

    def get_user_visits(self, user_id, subset=False, offset=0, limit=20):
        """
        Retrieve visits associated with a user.
        
        Args:
            user_id (str): The ID of the user.
            subset (bool, optional): If True, returns a subset of visits based on date criteria.
                                    If False, uses pagination with offset and limit. Defaults to False.
            offset (int, optional): Number of visits to skip for pagination. Defaults to 0.
            limit (int, optional): Maximum number of visits to return. Defaults to 20.
            
        Returns:
            list: A list of visit documents with decrypted fields, or empty list if error occurs.
        """
        try:
            user = self.get_user(user_id)
            visit_ids = [ObjectId(vid) for vid in user['visit_ids']]
            
            if subset:
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                query = {
                    '_id': {'$in': visit_ids},
                    'created_at': {'$gte': today, '$lt': today + timedelta(days=1)}
                }
                today_visits = list(self.visits.find(query).sort('created_at', -1))
                if len(today_visits) >= 10:
                    return [self.decrypt_visit(visit) for visit in today_visits]
                return [self.decrypt_visit(visit) for visit in 
                       self.visits.find({'_id': {'$in': visit_ids}}).sort('created_at', -1).limit(10)]
            else:
                return [self.decrypt_visit(visit) for visit in 
                       self.visits.find({'_id': {'$in': visit_ids}}).sort('created_at', -1).skip(offset).limit(limit)]
        except Exception as e:
            logger.error(f"get_user_visits error for user_id {user_id}: {str(e)}")
            return []

    def decrypt_template(self, template):
        """
        Decrypt and format a template document from the database.
        
        Args:
            template (dict): The encrypted template document from the database.
            
        Returns:
            dict: The decrypted template document with formatted fields, or None if error occurs.
            
        Note:
            Converts ObjectIds to strings and decrypts sensitive fields.
        """
        try:
            template_copy = template.copy()
            template_copy['template_id'] = str(template_copy['_id'])
            template_copy['user_id'] = str(template_copy['user_id'])
            template_copy['created_at'] = str(template_copy['created_at'])
            template_copy['modified_at'] = str(template_copy['modified_at'])
            template_copy['name'] = decrypt(template_copy['encrypt_name'])
            template_copy['instructions'] = decrypt(template_copy['encrypt_instructions'])
            template_copy['print'] = decrypt(template_copy['encrypt_print'])
            if 'encrypt_header' in template_copy: template_copy['header'] = decrypt(template_copy['encrypt_header'])
            if 'encrypt_footer' in template_copy: template_copy['footer'] = decrypt(template_copy['encrypt_footer'])
            del template_copy['_id']
            del template_copy['encrypt_name']
            del template_copy['encrypt_instructions']
            del template_copy['encrypt_print']
            if 'encrypt_header' in template_copy: del template_copy['encrypt_header']
            if 'encrypt_footer' in template_copy: del template_copy['encrypt_footer']
            return template_copy
        except Exception as e:
            logger.error(f"decrypt_template error for template_id {template.get('_id', 'unknown')}: {str(e)}")
            return None
    
    def create_template(self, user_id, status="READY", name="New Template", instructions=""):
        """
        Create a new template for a user.
        
        Args:
            user_id (str): The ID of the user who will own the template.
            
        Returns:
            dict: The newly created template document with decrypted fields, or None if creation failed.
            
        Note:
            The template is initialized with default values and added to the user's template_ids.
        """
        try:
            user = self.get_user(user_id)
            template = {
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'modified_at': datetime.utcnow(),
                'status': status,
                'encrypt_name': encrypt(name),
                'encrypt_instructions': encrypt(instructions),
                'encrypt_print': encrypt(''),
                'encrypt_header': encrypt(''),
                'encrypt_footer': encrypt(''),
                'note_generation_quality': 'BASIC',
            }
            self.templates.insert_one(template)
            self.users.update_one({'_id': ObjectId(user_id)}, {'$push': {'template_ids': template['_id']}})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"create_template error for user_id {user_id}: {str(e)}")
            return None

    def update_template(self, template_id, status=None, name=None, instructions=None, print=None, header=None, footer=None, note_generation_quality=None):
        """
        Update a template's information in the database.
        
        Args:
            template_id (str): The ID of the template to update.
            name (str, optional): The template's new name.
            instructions (str, optional): The template's new instructions.
            print (str, optional): The template's new print format.
            header (str, optional): The template's new header.
            footer (str, optional): The template's new footer.
            
        Returns:
            dict: The updated template document with decrypted fields, or None if update failed.
        """
        try:
            update_fields = {}
            if status is not None:
                update_fields['status'] = status
            if name is not None:
                update_fields['encrypt_name'] = encrypt(name)
            if instructions is not None:
                update_fields['encrypt_instructions'] = encrypt(instructions)
            if print is not None:
                update_fields['encrypt_print'] = encrypt(print)  
            if header is not None:
                update_fields['encrypt_header'] = encrypt(header)
            if footer is not None:
                update_fields['encrypt_footer'] = encrypt(footer)
            if note_generation_quality is not None:
                update_fields['note_generation_quality'] = note_generation_quality
            if instructions is not None:
                update_fields['modified_at'] = datetime.utcnow()
            if update_fields:
                self.templates.update_one({'_id': ObjectId(template_id)}, {'$set': update_fields})
            template = self.templates.find_one({'_id': ObjectId(template_id)})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"update_template error for template_id {template_id}: {str(e)}")
            return None

    def delete_template(self, template_id, user_id):
        """
        Delete a template from the database and remove it from the user's template list.
        
        Args:
            template_id (str): The ID of the template to delete.
            user_id (str): The ID of the user who owns the template.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            self.templates.delete_one({'_id': ObjectId(template_id)})
            self.users.update_one({'_id': ObjectId(user_id)}, {'$pull': {'template_ids': ObjectId(template_id)}})
            return True
        except Exception as e:
            logger.error(f"delete_template error for template_id {template_id}, user_id {user_id}: {str(e)}")
            return False

    def get_template(self, template_id):
        """
        Retrieve a template by its ID.
        
        Args:
            template_id (str): The ID of the template to retrieve.
            
        Returns:
            dict: The template document with decrypted fields, or None if not found or error occurs.
        """
        try:
            template = self.templates.find_one({'_id': ObjectId(template_id)})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"get_template error for template_id {template_id}: {str(e)}")
            return None
    
    def decrypt_visit(self, visit):
        """
        Decrypt and format a visit document from the database.
        
        Args:
            visit (dict): The encrypted visit document from the database.
            
        Returns:
            dict: The decrypted visit document with formatted fields, or None if error occurs.
            
        Note:
            Converts ObjectIds to strings and decrypts sensitive fields.
        """
        try:
            visit_copy = visit.copy()
            visit_copy['visit_id'] = str(visit_copy['_id'])
            visit_copy['user_id'] = str(visit_copy['user_id'])
            visit_copy['created_at'] = str(visit_copy['created_at'])
            visit_copy['modified_at'] = str(visit_copy['modified_at'])
            if visit_copy['template_modified_at']: visit_copy['template_modified_at'] = str(visit_copy['template_modified_at'])
            if visit_copy['recording_started_at']: visit_copy['recording_started_at'] = str(visit_copy['recording_started_at'])
            if visit_copy['recording_finished_at']: visit_copy['recording_finished_at'] = str(visit_copy['recording_finished_at'])
            visit_copy['name'] = decrypt(visit_copy['encrypt_name'])
            visit_copy['additional_context'] = decrypt(visit_copy['encrypt_additional_context'])
            visit_copy['transcript'] = decrypt(visit_copy['encrypt_transcript'])
            visit_copy['note'] = decrypt(visit_copy['encrypt_note'])
            del visit_copy['_id']
            del visit_copy['encrypt_name']
            del visit_copy['encrypt_additional_context']
            del visit_copy['encrypt_transcript']
            del visit_copy['encrypt_note']
            return visit_copy
        except Exception as e:
            logger.error(f"decrypt_visit error for visit_id {visit.get('_id', 'unknown')}: {str(e)}")
            return None
    
    def create_visit(self, user_id):
        """
        Create a new visit for a user.
        
        Args:
            user_id (str): The ID of the user who will own the visit.
            
        Returns:
            dict: The newly created visit document with decrypted fields, or None if creation failed.
            
        Note:
            The visit is initialized with default values and added to the user's visit_ids.
            Also updates the user's daily statistics.
        """
        try:
            user = self.get_user(user_id)
            visit = {
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'modified_at': datetime.utcnow(),
                'status': 'NOT_STARTED',
                'encrypt_name': encrypt(''),
                'template_modified_at': datetime.utcnow(),
                'template_id': user['default_template_id'],
                'language': user['default_language'],
                'encrypt_additional_context': encrypt(''),
                'recording_started_at': '',
                'recording_duration': '',
                'recording_finished_at': '',
                'encrypt_transcript': encrypt(''),
                'encrypt_note': encrypt(''),
            }
            self.visits.insert_one(visit)
            self.users.update_one({'_id': ObjectId(user_id)}, {'$push': {'visit_ids': visit['_id']}})
            self.update_daily_statistic(user_id, 'visits', 1)
            return self.decrypt_visit(visit)
        except Exception as e:
            logger.error(f"create_visit error for user_id {user_id}: {str(e)}")
            return None
    
    def update_visit(self, visit_id, status=None, name=None, template_modified_at=None, template_id=None, language=None, additional_context=None, recording_started_at=None, recording_duration=None, recording_finished_at=None, transcript=None, note=None):
        """
        Update a visit's information in the database.
        
        Args:
            visit_id (str): The ID of the visit to update.
            status (str, optional): The visit's new status.
            name (str, optional): The visit's new name.
            template_modified_at (datetime, optional): The timestamp when the template was last modified.
            template_id (str, optional): The ID of the template associated with the visit.
            language (str, optional): The language used for the visit.
            additional_context (str, optional): Additional context for the visit.
            recording_started_at (datetime, optional): The timestamp when recording started.
            recording_duration (str, optional): The duration of the recording.
            recording_finished_at (datetime, optional): The timestamp when recording finished.
            transcript (str, optional): The transcript of the visit.
            note (str, optional): Notes for the visit.
            
        Returns:
            dict: The updated visit document with decrypted fields, or None if update failed.
            
        Note:
            Updates the user's daily statistics if recording duration changes.
        """
        try:
            update_fields = {}
            if status is not None:
                update_fields['status'] = status
            if name is not None:
                update_fields['encrypt_name'] = encrypt(name)
            if template_modified_at is not None:
                update_fields['template_modified_at'] = template_modified_at
            if template_id is not None:
                update_fields['template_id'] = template_id
            if language is not None:
                update_fields['language'] = language
            if additional_context is not None:
                update_fields['encrypt_additional_context'] = encrypt(additional_context)
            if recording_started_at is not None:
                update_fields['recording_started_at'] = recording_started_at
            if recording_finished_at is not None:
                update_fields['recording_finished_at'] = recording_finished_at
            if transcript is not None:
                update_fields['encrypt_transcript'] = encrypt(transcript)
            if note is not None:
                update_fields['encrypt_note'] = encrypt(note)
            if recording_duration is not None:
                current_visit = self.visits.find_one({'_id': ObjectId(visit_id)})
                update_fields['recording_duration'] = recording_duration
                duration_increment = max(0, float(recording_duration or 0) - float(current_visit.get('recording_duration', 0) or 0))
                if duration_increment > 0:
                    self.update_daily_statistic(str(current_visit['user_id']), 'audio_time', duration_increment)
            if update_fields:
                update_fields['modified_at'] = datetime.utcnow()
                self.visits.update_one({'_id': ObjectId(visit_id)}, {'$set': update_fields})            
            visit = self.visits.find_one({'_id': ObjectId(visit_id)})
            return self.decrypt_visit(visit)
        except Exception as e:
            logger.error(f"update_visit error for visit_id {visit_id}: {str(e)}")
            return None

    def delete_visit(self, visit_id, user_id):
        """
        Delete a visit from the database and remove it from the user's visit list.
        
        Args:
            visit_id (str): The ID of the visit to delete.
            user_id (str): The ID of the user who owns the visit.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            self.visits.delete_one({'_id': ObjectId(visit_id)})
            self.users.update_one({'_id': ObjectId(user_id)}, {'$pull': {'visit_ids': ObjectId(visit_id)}})
            return True
        except Exception as e:
            logger.error(f"delete_visit error for visit_id {visit_id}, user_id {user_id}: {str(e)}")
            return False

    def get_visit(self, visit_id):
        """
        Retrieve a visit by its ID.
        
        Args:
            visit_id (str): The ID of the visit to retrieve.
            
        Returns:
            dict: The visit document with decrypted fields, or None if not found or error occurs.
        """
        try:
            visit = self.visits.find_one({'_id': ObjectId(visit_id)})
            return self.decrypt_visit(visit)
        except Exception as e:
            logger.error(f"get_visit error for visit_id {visit_id}: {str(e)}")
            return None

    def create_default_template(self, name, instructions, print='', header='', footer=''):
        """
        Create a default template available to all users.
        
        Args:
            name (str): The template's name.
            instructions (str): The template's instructions.
            print (str, optional): The template's print format. Defaults to empty string.
            header (str, optional): The template's header. Defaults to empty string.
            footer (str, optional): The template's footer. Defaults to empty string.
            
        Returns:
            dict: The newly created template document with decrypted fields, or None if creation failed.
            
        Note:
            This template is added to all users' template_ids and marked with 'DEFAULT' status.
        """
        try:
            template = {
                'user_id': 'HALO',
                'created_at': datetime.utcnow(),
                'modified_at': datetime.utcnow(),
                'status': 'DEFAULT',
                'encrypt_name': encrypt(name),
                'encrypt_instructions': encrypt(instructions),
                'encrypt_print': encrypt(print),
                'encrypt_header': encrypt(header),
                'encrypt_footer': encrypt(footer),
                'note_generation_quality': 'BASIC',
            }
            self.templates.insert_one(template)
            self.users.update_many({}, {'$push': {'template_ids': template['_id']}})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"create_default_template error for name {name}: {str(e)}")
            return None

    def update_default_template(self, template_id, name=None, instructions=None, print=None, header=None, footer=None, note_generation_quality=None):
        """
        Update a default template.
        
        Args:
            template_id (str): The ID of the default template to update.
            name (str, optional): The template's new name.
            instructions (str): The new instructions for the template.
            print (str, optional): The template's new print format.
            header (str, optional): The template's new header.
            footer (str, optional): The template's new footer.

        Returns:
            dict: The updated template document with decrypted fields, or None if update failed.
        """
        try:
            update_fields = {}
            if name is not None:
                update_fields['encrypt_name'] = encrypt(name)
            if instructions is not None:
                update_fields['encrypt_instructions'] = encrypt(instructions)
            if print is not None:
                update_fields['encrypt_print'] = encrypt(print)
            if header is not None:
                update_fields['encrypt_header'] = encrypt(header)
            if footer is not None:
                update_fields['encrypt_footer'] = encrypt(footer)
            if note_generation_quality is not None:
                update_fields['note_generation_quality'] = note_generation_quality
            if update_fields:
                update_fields['modified_at'] = datetime.utcnow()
                self.templates.update_one({'_id': ObjectId(template_id)}, {'$set': update_fields})
            template = self.templates.find_one({'_id': ObjectId(template_id)})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"update_default_template error for template_id {template_id}: {str(e)}")

    def delete_default_template(self, template_id):
        """
        Delete a default template and remove it from all users' template lists.
        
        Args:
            template_id (str): The ID of the default template to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            self.templates.delete_one({'_id': ObjectId(template_id)})
            self.users.update_many({}, {'$pull': {'template_ids': ObjectId(template_id)}})
            return True
        except Exception as e:
            logger.error(f"delete_default_template error for template_id {template_id}: {str(e)}")
            return False

    def get_default_template(self, template_id):
        """
        Retrieve a default template by its ID.
        
        Args:
            template_id (str): The ID of the default template to retrieve.
            
        Returns:
            dict: The template document with decrypted fields, or None if not found or error occurs.
        """
        try:
            template = self.templates.find_one({'_id': ObjectId(template_id)})
            return self.decrypt_template(template)
        except Exception as e:
            logger.error(f"get_default_template error for template_id {template_id}: {str(e)}")
            return None
    
    def get_all_default_templates(self):
        """
        Retrieve all templates from the database with status 'DEFAULT'.
        
        Returns:
            list: A list of template documents with status 'DEFAULT' and decrypted fields.
        """
        try:
            templates = self.templates.find({'status': 'DEFAULT'})
            return [self.decrypt_template(template) for template in templates]
        except Exception as e:
            logger.error(f"get_all_default_templates error: {str(e)}")
            return []

    def update_daily_statistic(self, user_id, stat_type, value):
        """
        Update a user's daily statistics.
        
        Args:
            user_id (str): The ID of the user whose statistics to update.
            stat_type (str): The type of statistic to update ('visits' or 'audio_time').
            value: The value to add to the statistic.
            
        Note:
            Creates a new daily record if one doesn't exist for today.
            For 'visits', increments by 1.
            For 'audio_time', increments by the provided value.
        """
        try:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            self.users.update_one(
                {'_id': ObjectId(user_id), f'daily_statistics.{today}': {'$exists': False}},
                {'$set': {f'daily_statistics.{today}': {'visits': 0, 'audio_time': 0}}}
            )
            if stat_type == 'visits':
                self.users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$inc': {f'daily_statistics.{today}.visits': 1}}
                )
            elif stat_type == 'audio_time':
                if isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        value = 0
                self.users.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$inc': {f'daily_statistics.{today}.audio_time': value}}
                )
        except Exception as e:
            logger.error(f"update_daily_statistic error for user_id {user_id}, stat_type {stat_type}, value {value}: {str(e)}")

    def decrypt_admin(self, admin):
        """
        Decrypt and format an admin document from the database.
        
        Args:
            admin (dict): The encrypted admin document from the database.
            
        Returns:
            dict: The decrypted admin document with formatted fields, or None if error occurs.
            
        Note:
            Converts ObjectIds to strings and decrypts sensitive fields.
        """
        try:
            admin_copy = admin.copy()
            admin_copy['admin_id'] = str(admin_copy['_id'])
            admin_copy['created_at'] = str(admin_copy['created_at'])
            admin_copy['modified_at'] = str(admin_copy['modified_at'])
            admin_copy['name'] = decrypt(admin_copy['encrypt_name'])
            admin_copy['email'] = decrypt(admin_copy['encrypt_email'])
            admin_copy['master_note_generation_instructions'] = decrypt(admin_copy['encrypt_master_note_generation_instructions'])
            admin_copy['master_template_polish_instructions'] = decrypt(admin_copy['encrypt_master_template_polish_instructions'])
            del admin_copy['_id']
            del admin_copy['encrypt_name']
            del admin_copy['encrypt_email']
            del admin_copy['hashed_password']
            del admin_copy['encrypt_master_note_generation_instructions']
            del admin_copy['encrypt_master_template_polish_instructions']
            return admin_copy
        except Exception as e:
            logger.error(f"decrypt_admin error for admin_id {admin.get('_id', 'unknown')}: {str(e)}")
            return None

    def create_admin(self, name, email, password, master_note_generation_instructions='', master_template_polish_instructions=''):
        """
        Create a new admin in the database.
        
        Args:
            name (str): The admin's name.
            email (str): The admin's email address.
            password (str): The admin's password.
            master_note_generation_instructions (str, optional): Master instructions for note generation.
            master_template_polish_instructions (str, optional): Master instructions for template polishing.
            
        Returns:
            dict: The newly created admin document with decrypted fields, or None if creation failed.
            
        Note:
            Checks for existing admins with the same email before creation.
        """
        try:
            encrypted_email = encrypt(email)
            all_admins = list(self.admins.find())
            for admin in all_admins:
                decrypted_email = decrypt(admin['encrypt_email'])
                if decrypted_email == email:
                    return None
            admin = {
                'created_at': datetime.utcnow(),
                'modified_at': datetime.utcnow(),
                'status': 'ADMIN',
                'encrypt_name': encrypt(name),
                'encrypt_email': encrypted_email,
                'hashed_password': hash_password(password),
                'encrypt_master_note_generation_instructions': encrypt(master_note_generation_instructions),
                'encrypt_master_template_polish_instructions': encrypt(master_template_polish_instructions)
            }
            self.admins.insert_one(admin)
            return self.decrypt_admin(admin)
        except Exception as e:
            logger.error(f"create_admin error for email {email}: {str(e)}")
            return None

    def update_admin(self, admin_id, master_note_generation_instructions=None, master_template_polish_instructions=None):
        """
        Update an admin's information in the database.
        
        Args:
            admin_id (str): The ID of the admin to update.
            name (str, optional): The admin's new name.
            email (str, optional): The admin's new email address.
            password (str, optional): The admin's new password.
            status (str, optional): The admin's new status.
            master_note_generation_instructions (str, optional): The admin's new master note generation instructions.
            master_template_polish_instructions (str, optional): The admin's new master template polish instructions.
            
        Returns:
            dict: The updated admin document with decrypted fields, or None if update failed.
        """
        try:
            update_fields = {}
            if master_note_generation_instructions is not None:
                update_fields['encrypt_master_note_generation_instructions'] = encrypt(master_note_generation_instructions)
            if master_template_polish_instructions is not None:
                update_fields['encrypt_master_template_polish_instructions'] = encrypt(master_template_polish_instructions)
            if update_fields:
                update_fields['modified_at'] = datetime.utcnow()
                self.admins.update_one({'_id': ObjectId(admin_id)}, {'$set': update_fields})
            admin = self.admins.find_one({'_id': ObjectId(admin_id)})
            return self.decrypt_admin(admin)
        except Exception as e:
            logger.error(f"update_admin error for admin_id {admin_id}: {str(e)}")
            return None

    def delete_admin(self, admin_id):
        """
        Delete an admin from the database.
        
        Args:
            admin_id (str): The ID of the admin to delete.
            
        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        try:
            self.admins.delete_one({'_id': ObjectId(admin_id)})
            return True
        except Exception as e:
            logger.error(f"delete_admin error for admin_id {admin_id}: {str(e)}")
            return False

    def get_admin(self, admin_id=None):
        """
        Retrieve the admin. Since there's only one admin in the system, 
        this method will return the first admin found if no ID is provided.
        
        Args:
            admin_id (str, optional): The ID of the admin to retrieve.
            
        Returns:
            dict: The admin document with decrypted fields, or None if not found or error occurs.
        """
        try:
            if admin_id:
                admin = self.admins.find_one({'_id': ObjectId(admin_id)})
            else:
                admin = self.admins.find_one()
            
            return self.decrypt_admin(admin) if admin else None
        except Exception as e:
            logger.error(f"get_admin error for admin_id {admin_id}: {str(e)}")
            return None

    def get_admin_by_email(self, email):
        """
        Retrieve an admin by their email address.
        
        Args:
            email (str): The email address to search for.
            
        Returns:
            dict: The admin document with decrypted fields, or None if not found or error occurs.
        """
        try:
            all_admins = list(self.admins.find())
            for admin in all_admins:
                decrypted_email = decrypt(admin['encrypt_email'])
                if decrypted_email == email:
                    return self.decrypt_admin(admin)
            return None
        except Exception as e:
            logger.error(f"get_admin_by_email error for email {email}: {str(e)}")
            return None

    def verify_admin(self, email, password):
        """
        Verify an admin's login credentials.
        
        Args:
            email (str): The admin's email address.
            password (str): The admin's password.
            
        Returns:
            dict: The admin document with decrypted fields if credentials are valid, None otherwise.
        """
        try:
            hashed_password = hash_password(password)
            all_admins = list(self.admins.find())
            for admin in all_admins:
                decrypted_email = decrypt(admin['encrypt_email'])
                if decrypted_email == email and admin['hashed_password'] == hashed_password:
                    return self.decrypt_admin(admin)
            return None
        except Exception as e:
            logger.error(f"verify_admin error for email {email}: {str(e)}")
            return None


    def set_verification_code(self, user_id, code):
        """
        Set email verification code for a user.
        
        Args:
            user_id (str): The ID of the user.
            code (str): The verification code to set.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            expires_at = datetime.utcnow() + timedelta(hours=1)
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'miscellaneous.verification_code': code,
                    'miscellaneous.verification_expires_at': expires_at
                }}
            )
            return True
        except Exception as e:
            logger.error(f"set_verification_code error for user_id {user_id}: {str(e)}")
            return False
    
    def verify_email_code(self, user_id, code):
        """
        Verify email verification code and activate user if valid.
        
        Args:
            user_id (str): The ID of the user.
            code (str): The verification code to verify.
            
        Returns:
            bool: True if verification successful, False otherwise.
        """
        try:
            user = self.users.find_one({'_id': ObjectId(user_id)})
            if not user:
                return False
            
            miscellaneous = user.get('miscellaneous', {})
            if miscellaneous.get('verification_code') != code:
                return False
            
            if miscellaneous.get('verification_expires_at') and miscellaneous['verification_expires_at'] < datetime.utcnow():
                return False
            
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'status': 'ACTIVE',
                    'miscellaneous.verification_code': None,
                    'miscellaneous.verification_expires_at': None,
                    'modified_at': datetime.utcnow()
                }}
            )
            return True
        except Exception as e:
            logger.error(f"verify_email_code error for user_id {user_id}: {str(e)}")
            return False
    
    def set_reset_code(self, user_id, code):
        """
        Set password reset code for a user.
        
        Args:
            user_id (str): The ID of the user.
            code (str): The reset code to set.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            expires_at = datetime.utcnow() + timedelta(hours=1)
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'miscellaneous.reset_code': code,
                    'miscellaneous.reset_expires_at': expires_at
                }}
            )
            return True
        except Exception as e:
            logger.error(f"set_reset_code error for user_id {user_id}: {str(e)}")
            return False
    
    def verify_reset_code(self, email, code):
        """
        Verify password reset code.
        
        Args:
            email (str): The user's email address.
            code (str): The reset code to verify.
            
        Returns:
            str: The user_id if verification successful, None otherwise.
        """
        try:
            user = self.get_user_by_email(email)
            if not user:
                return None
                
            raw_user = self.users.find_one({'_id': ObjectId(user['user_id'])})
            miscellaneous = raw_user.get('miscellaneous', {})
            
            if miscellaneous.get('reset_code') != code:
                return None
            
            if miscellaneous.get('reset_expires_at') and miscellaneous['reset_expires_at'] < datetime.utcnow():
                return None
            
            return user['user_id']
        except Exception as e:
            logger.error(f"verify_reset_code error for email {email}: {str(e)}")
            return None
    
    def reset_password(self, user_id, new_password):
        """
        Reset user's password and clear reset code.
        
        Args:
            user_id (str): The ID of the user.
            new_password (str): The new password.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {
                    'hash_password': hash_password(new_password),
                    'miscellaneous.reset_code': None,
                    'miscellaneous.reset_expires_at': None,
                    'modified_at': datetime.utcnow()
                }}
            )
            return True
        except Exception as e:
            logger.error(f"reset_password error for user_id {user_id}: {str(e)}")
            return False

    def update_user_subscription(self, user_id, plan, stripe_customer_id=None, stripe_subscription_id=None):
        """
        Update user's subscription information.
        
        Args:
            user_id (str): The ID of the user.
            plan (str): The subscription plan (NO_PLAN, CANCELLED, FREE, MONTHLY, YEARLY, CUSTOM).
            stripe_customer_id (str, optional): The Stripe customer ID.
            stripe_subscription_id (str, optional): The Stripe subscription ID.
        Returns:
            dict: The updated user document with decrypted fields, or None if update failed.
        """
        try:
            update_fields = {
                'subscription.plan': plan,
                'modified_at': datetime.utcnow()
            }
            if stripe_customer_id is not None:
                update_fields['subscription.stripe_customer_id'] = stripe_customer_id
            if stripe_subscription_id is not None:
                update_fields['subscription.stripe_subscription_id'] = stripe_subscription_id
            
            self.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            user = self.users.find_one({'_id': ObjectId(user_id)})
            return self.decrypt_user(user)
        except Exception as e:
            logger.error(f"update_user_subscription error for user_id {user_id}: {str(e)}")
            return None

    def start_free_trial(self, user_id):
        """
        Start free trial for a user.
        
        Args:
            user_id (str): The ID of the user.
            
        Returns:
            dict: The updated user document with decrypted fields, or None if update failed.
        """
        try:
            expiration_date = datetime.utcnow() + timedelta(days=7)
            update_fields = {
                'subscription.plan': 'FREE',
                'subscription.free_trial_used': True,
                'subscription.free_trial_expiration_date': expiration_date,
                'modified_at': datetime.utcnow()
            }
            self.users.update_one({'_id': ObjectId(user_id)}, {'$set': update_fields})
            user = self.users.find_one({'_id': ObjectId(user_id)})
            return self.decrypt_user(user)
        except Exception as e:
            logger.error(f"start_free_trial error for user_id {user_id}: {str(e)}")
            return None

    def check_trial_expired(self, user_id):
        """
        Check if user's free trial has expired.
        
        Args:
            user_id (str): The ID of the user.
            
        Returns:
            bool: True if trial has expired, False otherwise.
        """
        try:
            user = self.get_user(user_id)
            if not user or user.get('subscription', {}).get('plan') != 'FREE':
                return False
            
            expiration_date = user.get('subscription', {}).get('free_trial_expiration_date')
            if not expiration_date:
                return False
            
            expiration_datetime = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
            return datetime.utcnow() > expiration_datetime
        except Exception as e:
            logger.error(f"check_trial_expired error for user_id {user_id}: {str(e)}")
            return False

    def migrate_users_to_new_format(self):
        """
        Migrate all existing users from old format to new format.
        This method should be run once to update the database structure.
        
        Returns:
            dict: Migration results with counts of updated users.
        """
        try:
            logger.info("Starting user migration to new format...")
            old_format_users = list(self.users.find({
                '$or': [
                    {'subscription_status': {'$exists': True}},
                    {'verification_code': {'$exists': True}},
                    {'reset_code': {'$exists': True}}
                ]
            }))

            migrated_count = 0
            error_count = 0
            
            for user in old_format_users:
                try:
                    user_id = user['_id']
                    update_fields = {}
                    
                    if 'subscription_status' in user:
                        subscription_status = user.get('subscription_status', 'INACTIVE')
                        if subscription_status == 'ACTIVE':
                            plan = user.get('subscription_plan', 'MONTHLY')
                        elif subscription_status == 'FREE_TRIAL':
                            plan = 'FREE'
                        elif subscription_status == 'CANCELLED':
                            plan = 'CANCELLED'
                        else:
                            plan = 'NO_PLAN'
                        
                        update_fields['subscription'] = {
                            'plan': plan,
                            'free_trial_used': user.get('free_trial_used', False),
                            'free_trial_expiration_date': user.get('free_trial_expiration_date'),
                            'stripe_customer_id': user.get('stripe_customer_id'),
                            'stripe_subscription_id': user.get('stripe_subscription_id')
                        }
                        
                        update_fields['$unset'] = {
                            'subscription_status': '',
                            'subscription_plan': '',
                            'free_trial_used': '',
                            'free_trial_expiration_date': '',
                            'stripe_customer_id': '',
                            'stripe_subscription_id': ''
                        }
                    
                    if any(field in user for field in ['verification_code', 'verification_expires_at', 'reset_code', 'reset_expires_at']):
                        update_fields['miscellaneous'] = {
                            'verification_code': user.get('verification_code'),
                            'verification_expires_at': user.get('verification_expires_at'),
                            'reset_code': user.get('reset_code'),
                            'reset_expires_at': user.get('reset_expires_at')
                        }
                        
                        if '$unset' not in update_fields:
                            update_fields['$unset'] = {}
                        update_fields['$unset'].update({
                            'verification_code': '',
                            'verification_expires_at': '',
                            'reset_code': '',
                            'reset_expires_at': ''
                        })
                    
                    if update_fields:
                        unset_fields = update_fields.pop('$unset', {})
                        
                        self.users.update_one(
                            {'_id': user_id},
                            {'$set': update_fields}
                        )
                        
                        if unset_fields:
                            self.users.update_one(
                                {'_id': user_id},
                                {'$unset': unset_fields}
                            )
                        
                        migrated_count += 1
                        logger.info(f"Migrated user {user_id}")
                
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error migrating user {user.get('_id', 'unknown')}: {str(e)}")
            
            result = {
                'total_users_found': len(old_format_users),
                'migrated_successfully': migrated_count,
                'errors': error_count
            }
            
            logger.info(f"Migration completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            return {'error': str(e)}


db = database()