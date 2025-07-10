import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os
from dotenv import load_dotenv
from typing import List, Dict, Optional

INSTRUCTIONS = """
Generate everything to the best of your ability.
"""
JSON_SCHEMA = """
{
    "note": "string; use \n to separate paragraphs"
}
"""

def verify(username: str, password: str, office_key: str, app_name: str) -> bool:
    """
    Verify AdvancedMD credentials by attempting to authenticate.
    
    Args:
        username: AdvancedMD username
        password: AdvancedMD password  
        office_key: AdvancedMD office key
        app_name: AdvancedMD app name
        
    Returns:
        True if credentials are valid, False otherwise
    """
    initial_api_url = "https://partnerlogin.advancedmd.com/practicemanager/xmlrpc/processrequest.aspx"
    current_time = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    login_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ppmdmsg action="login" class="login" msgtime="{current_time}" username="{username}" psw="{password}" officecode="{office_key}" appname="{app_name}"/>
"""
    headers = {'Content-Type': 'text/xml', 'Accept': 'text/xml'}
    
    try:
        response = requests.post(initial_api_url, headers=headers, data=login_xml, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        results = root.find('Results')
        
        if results is not None and results.get('success') == '0':
            usercontext = results.find('usercontext')
            if usercontext is not None:
                webserver = usercontext.get('webserver')
                if webserver:
                    api_version = webserver.split('/')[-2]
                    redirect_url = f"https://providerapi.advancedmd.com/processrequest/{api_version}/{app_name}/xmlrpc/processrequest.aspx"
                    response = requests.post(redirect_url, headers=headers, data=login_xml, timeout=30)
                    response.raise_for_status()
                    root = ET.fromstring(response.text)
                    results = root.find('Results')
        
        if results is not None and results.get('success') == '1':
            usercontext = results.find('usercontext')
            if usercontext is not None and usercontext.text:
                return True
        
        return False
        
    except (requests.exceptions.RequestException, ET.ParseError, Exception):
        return False

def get_patients(username: str, password: str, office_key: str, app_name: str, target_date: Optional[str] = None) -> List[Dict]:
    """
    Get patients with their appointment details for a specific date.
    
    Args:
        username: AdvancedMD username
        password: AdvancedMD password
        office_key: AdvancedMD office key
        app_name: AdvancedMD app name
        target_date: Date string in format "MM/DD/YYYY". If None, uses today's date.
        
    Returns:
        List of dictionaries with patient_id, patient_name, and patient_details (appt date and time as string)
    """
    
    target_date = target_date or datetime.now().strftime("%m/%d/%Y")
    if isinstance(target_date, datetime):
        target_date = target_date.strftime("%m/%d/%Y")
    
    initial_api_url = "https://partnerlogin.advancedmd.com/practicemanager/xmlrpc/processrequest.aspx"
    current_time = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
    login_xml = f'<?xml version="1.0" encoding="UTF-8"?><ppmdmsg action="login" class="login" msgtime="{current_time}" username="{username}" psw="{password}" officecode="{office_key}" appname="{app_name}"/>'
    headers = {'Content-Type': 'text/xml', 'Accept': 'text/xml'}
    
    try:
        response = requests.post(initial_api_url, headers=headers, data=login_xml, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        results = root.find('Results')
        
        if results is not None and results.get('success') == '0':
            usercontext = results.find('usercontext')
            if usercontext is not None and usercontext.get('webserver'):
                api_version = usercontext.get('webserver').split('/')[-2]
                redirect_url = f"https://providerapi.advancedmd.com/processrequest/{api_version}/{app_name}/xmlrpc/processrequest.aspx"
                response = requests.post(redirect_url, headers=headers, data=login_xml, timeout=30)
                response.raise_for_status()
                root = ET.fromstring(response.text)
                results = root.find('Results')
        
        if not (results is not None and results.get('success') == '1'):
            raise Exception("Failed to authenticate with AdvancedMD")
        
        usercontext = results.find('usercontext')
        token = usercontext.text
        webserver_url = usercontext.get('webserver')
        
        headers["Cookie"] = f"token={token}"
        api_version = webserver_url.split('/')[-2]
        api_url = f"https://providerapi.advancedmd.com/processrequest/{api_version}/{app_name}/xmlrpc/processrequest.aspx"
        
        visits_xml = f'<ppmdmsg action="getdatevisits" class="api" msgtime="{datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")}" visitdate="{target_date}"><visit columnheading="ColumnHeading" duration="Duration" color="Color" apptstatus="ApptStatus" visitdate="VisitDate" visitstarttime="VisitStartTime"/><patient name="Name" ssn="SSN" changedat="ChangedAt" createdat="CreatedAt"/><insurance carname="CarName" carcode="CarCode" changedat="ChangedAt" createdat="CreatedAt"/></ppmdmsg>'
        
        response = requests.post(api_url, headers=headers, data=visits_xml, timeout=30)
        response.raise_for_status()
        
        root = ET.fromstring(response.text)
        results = root.find('Results')
        patients = []
        processed_patient_ids = set()
        
        if results is not None:
            visitlist = results.find('visitlist')
            if visitlist is not None:
                for visit in visitlist.findall('visit'):
                    patientlist = visit.find('patientlist')
                    if patientlist is not None:
                        patient = patientlist.find('patient')
                        if patient is not None:
                            patient_id = patient.get('id')
                            if patient_id and patient_id not in processed_patient_ids:
                                processed_patient_ids.add(patient_id)
                                appointment_date = visit.get('visitdate', target_date)
                                appointment_time = visit.get('visitstarttime', 'Unknown time')
                                patients.append({
                                    "patient_id": patient_id,
                                    "patient_name": patient.get('name', 'Unknown'),
                                    "patient_details": f"{appointment_date} {appointment_time}"
                                })
        
        return patients
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
    except ET.ParseError as e:
        raise Exception(f"XML parsing error: {str(e)}")
    except Exception as e:
        raise Exception(f"Error retrieving patients: {str(e)}")


def create_note(username: str, password: str, office_key: str, app_name: str,
                patient_id: str, payload: dict) -> bool:
    """
    Self-contained function to authenticate and create a note in AdvancedMD.
    
    Args:
        username: AdvancedMD username
        password: AdvancedMD password  
        office_key: AdvancedMD office key
        app_name: AdvancedMD app name
        patient_id: Patient ID to attach the note to
        payload: Payload containing note content text
        
    Returns:
        bool: True if note was created successfully, False otherwise
    """
    print(payload)
    
    def _login() -> Optional[tuple]:
        """Login and get token and webserver URL."""
        initial_api_url = "https://partnerlogin.advancedmd.com/practicemanager/xmlrpc/processrequest.aspx"
        current_time = datetime.now().strftime("%m/%d/%Y %I:%M:%S %p")
        
        login_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ppmdmsg action="login" class="login" msgtime="{current_time}" username="{username}" psw="{password}" officecode="{office_key}" appname="{app_name}"/>
"""
        
        headers = {'Content-Type': 'text/xml', 'Accept': 'text/xml'}
        
        try:
            response = requests.post(initial_api_url, headers=headers, data=login_xml)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            results = root.find('Results')
            
            if results is not None and results.get('success') == '0':
                usercontext = results.find('usercontext')
                if usercontext is not None:
                    webserver = usercontext.get('webserver')
                    if webserver:
                        api_version = webserver.split('/')[-2]
                        redirect_url = f"https://providerapi.advancedmd.com/processrequest/{api_version}/{app_name}/xmlrpc/processrequest.aspx"
                        
                        # Retry login with redirected URL
                        response = requests.post(redirect_url, headers=headers, data=login_xml)
                        response.raise_for_status()
                        root = ET.fromstring(response.text)
                        results = root.find('Results')
            
            # Extract token and webserver URL
            if results is not None and results.get('success') == '1':
                usercontext = results.find('usercontext')
                if usercontext is not None:
                    token = usercontext.text
                    webserver_url = usercontext.get('webserver')
                    return token, webserver_url
                    
            return None
            
        except Exception as e:
            print(f"Login failed: {e}")
            return None
    
    def _create_halo_note(token: str, webserver_url: str) -> bool:
        """Create note using Halo Custom template."""
        TEMPLATE_NAME = "Halo Custom"
        PAGE_INDEX = "1"
        FIELD_NAME = "note"
        FIELD_ID = "228173"
        PROFILE_ID = "485"
        
        now = datetime.now()
        msgtime = now.strftime("%m/%d/%Y %I:%M:%S %p")
        note_datetime = now.strftime("%m/%d/%Y %I:%M:%S %p")
        
        xml = f'''<ppmdmsg action="addehrnote" class="api" msgtime="{msgtime}" templatename="{TEMPLATE_NAME}" patientid="{patient_id}" profileid="{PROFILE_ID}" notedatetime="{note_datetime}">
    <pagelist>
        <page pageindex="{PAGE_INDEX}" pagename="Note">
            <fieldlist>
                <field pageindex="{PAGE_INDEX}" ordinal="{FIELD_ID}" fieldname="{FIELD_NAME}" requiredflag="0" enabledflag="-1" type="1" value="{payload['note']}" />
            </fieldlist>
        </page>
    </pagelist>
</ppmdmsg>'''
        
        api_version = webserver_url.split('/')[-2]
        api_url = f"https://providerapi.advancedmd.com/processrequest/{api_version}/{app_name}/xmlrpc/processrequest.aspx"
        
        headers = {
            'Content-Type': 'text/xml',
            'Accept': 'text/xml',
            'Cookie': f'token={token}'
        }
        
        try:
            response = requests.post(api_url, headers=headers, data=xml)
            response.raise_for_status()
            
            root = ET.fromstring(response.text)
            
            results_elem = root.find('Results')
            if results_elem is not None and results_elem.attrib.get('id'):
                return True
                
            if root.attrib.get('newid'):
                return True
                
            error_elem = root.find('Error')
            if error_elem is not None:
                fault = error_elem.find('.//Fault')
                if fault is not None:
                    return False
                    
            if results_elem is not None and error_elem is None:
                return True
                
            return False
            
        except Exception as e:
            print(f"Note creation failed: {e}")
            return False
    
    try:
        login_result = _login()
        if not login_result:
            return False
        token, webserver_url = login_result
        return _create_halo_note(token, webserver_url)
        
    except Exception as e:
        print(f"Error in create_note: {e}")
        return False
