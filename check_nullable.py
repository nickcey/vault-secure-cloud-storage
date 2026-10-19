from app import app, db
from database.models import FileMetadata

with app.app_context():
    print(f"filename nullable: {FileMetadata.__table__.columns['filename'].nullable}")
    print(f"encrypted_filename nullable: {FileMetadata.__table__.columns['encrypted_filename'].nullable}")
    print(f"file_size nullable: {FileMetadata.__table__.columns['file_size'].nullable}")
