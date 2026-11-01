import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage

class PrivateDocumentStorage(FileSystemStorage):
    """
    Dedicated private storage for customer-uploaded documents.
    Files are stored strictly outside the application source code directory.
    Direct public web server access is disabled.
    """
    def __init__(self, *args, **kwargs):
        storage_root = getattr(
            settings,
            'PRINTX_PRIVATE_STORAGE_ROOT',
            os.path.join(settings.BASE_DIR.parent, 'private_printx_storage', 'documents')
        )
        kwargs['location'] = storage_root
        kwargs['base_url'] = None  # Explicitly prevent direct public URL generation
        super().__init__(*args, **kwargs)
