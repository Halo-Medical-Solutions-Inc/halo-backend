from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from app.config import settings

def extract_text_from_file(file_url: str = None, file_path: str = None) -> str:
    client = DocumentIntelligenceClient(endpoint="https://revo-ocr-test.cognitiveservices.azure.com/", credential=AzureKeyCredential(settings.AZURE_API_KEY))
    
    if file_path:
        with open(file_path, "rb") as file:
            poller = client.begin_analyze_document("prebuilt-read", AnalyzeDocumentRequest(bytes_source=file.read()))
    elif file_url:
        poller = client.begin_analyze_document("prebuilt-read", AnalyzeDocumentRequest(url_source=file_url))
    else:
        raise ValueError("Either file_url or file_path must be provided")
    
    result = poller.result()
    return result.content or ""

def extract_text_from_bytes(file_bytes: bytes) -> str:
    """
    Extract text from file bytes using Azure Document Intelligence.
    
    Args:
        file_bytes: The file content as bytes
        
    Returns:
        str: The extracted text content
    """
    client = DocumentIntelligenceClient(
        endpoint="https://revo-ocr-test.cognitiveservices.azure.com/", 
        credential=AzureKeyCredential(settings.AZURE_API_KEY)
    )
    
    poller = client.begin_analyze_document(
        "prebuilt-read", 
        AnalyzeDocumentRequest(bytes_source=file_bytes)
    )
    
    result = poller.result()
    return result.content or ""
