class FileStorage:
    def __init__(self):
        self.storage = {}

    def upload_file(self, file_path, user_id):
        # Generate unique ID
        file_id = str(uuid.uuid4())
        # Validate file extension
        if not file_path.lower().endswith(('.pdf', '.docx', '.txt')):
            raise ValueError('Unsupported file type')
        # Calculate SHA-256 hash
        with open(file_path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        # Store metadata
        self.storage[file_id] = {
            'original_filename': os.path.basename(file_path),
            'safe_filename': self._sanitize_filename(os.path.basename(file_path)),
            'file_type': self._get_file_type(file_path),
            'file_size': os.path.getsize(file_path),
            'sha256_hash': file_hash,
            'upload_time': datetime.now().isoformat(),
            'user_id': user_id
        }
        return file_id

    def _sanitize_filename(self, filename):
        # Remove special characters and limit length
        return ''.join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip()[:50]

    def _get_file_type(self, path):
        # Map extensions to types
        ext = os.path.splitext(path)[1].lower()
        return 'pdf' if ext == '.pdf' else 'docx' if ext == '.docx' else 'txt'

    def get_file_metadata(self, file_id):
        return self.storage.get(file_id, {})