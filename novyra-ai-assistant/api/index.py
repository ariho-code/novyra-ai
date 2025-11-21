"""
Vercel serverless function entry point for Django
"""
import os
import sys
from pathlib import Path

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'novyra_ai.settings')
os.environ.setdefault('VERCEL', '1')

# Import Django
import django
django.setup()

# Import WSGI application
from novyra_ai.wsgi import application

# Vercel handler
from vercel import Request, Response

def handler(request: Request):
    """
    Vercel serverless function handler for Django
    """
    from io import BytesIO
    
    # Get request body
    body = b''
    if hasattr(request, 'body'):
        if isinstance(request.body, bytes):
            body = request.body
        elif isinstance(request.body, str):
            body = request.body.encode('utf-8')
    
    # Get query string
    query_string = ''
    if hasattr(request, 'query_string'):
        if isinstance(request.query_string, bytes):
            query_string = request.query_string.decode('utf-8')
        else:
            query_string = str(request.query_string or '')
    
    # Get path
    path = request.path if hasattr(request, 'path') else '/'
    
    # Get host
    host = request.headers.get('host', 'localhost')
    server_name = host.split(':')[0] if ':' in host else host
    server_port = host.split(':')[1] if ':' in host else '80'
    
    # Build WSGI environ
    environ = {
        'REQUEST_METHOD': request.method,
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'CONTENT_TYPE': request.headers.get('content-type', ''),
        'CONTENT_LENGTH': str(len(body)),
        'SERVER_NAME': server_name,
        'SERVER_PORT': server_port,
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https' if request.headers.get('x-forwarded-proto') == 'https' else 'http',
        'wsgi.input': BytesIO(body),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': True,
        'wsgi.run_once': False,
    }
    
    # Add HTTP headers
    for key, value in request.headers.items():
        key_upper = key.upper().replace('-', '_')
        if key_upper not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            environ[f'HTTP_{key_upper}'] = value
    
    # Response data
    response_data = {'status': 200, 'headers': [], 'body': b''}
    
    def start_response(status, headers):
        response_data['status'] = int(status.split()[0])
        response_data['headers'] = headers
    
    # Call WSGI application
    try:
        response_body = application(environ, start_response)
        
        # Collect response body
        body_parts = []
        for part in response_body:
            if isinstance(part, bytes):
                body_parts.append(part)
            else:
                body_parts.append(str(part).encode('utf-8'))
        response_data['body'] = b''.join(body_parts)
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        response_data['status'] = 500
        response_data['headers'] = [('Content-Type', 'text/plain')]
        response_data['body'] = error_msg.encode('utf-8')
    
    # Convert headers to dict
    headers_dict = {}
    for key, value in response_data['headers']:
        headers_dict[key] = value
    
    return Response(
        response_data['body'],
        status=response_data['status'],
        headers=headers_dict
    )

# Export for Vercel
def app(request: Request):
    return handler(request)

