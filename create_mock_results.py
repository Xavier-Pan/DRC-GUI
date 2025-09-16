#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv
from tasks import CustomFTP_TLS

# Load environment variables
load_dotenv()

FTP_CONFIG = {
    'host': os.getenv('FTP_SERVER_B_HOST'),
    'port': int(os.getenv('FTP_SERVER_B_PORT', '21')),
    'username': os.getenv('FTP_SERVER_B_USER'),
    'password': os.getenv('FTP_SERVER_B_PASS'),
    'download_dir': os.getenv('FTP_SERVER_B_DOWNLOAD_DIR', '/results')
}

def create_mock_batch_files(task_id: str):
    """Create mock batch result files (ZIP + manifest) for testing"""
    import zipfile
    import json
    from datetime import datetime
    
    # Use multiple real test image files
    test_image_patterns = ["test_drc*.png"]
    test_images = []
    
    # Find all test_drc*.png files
    for pattern in test_image_patterns:
        test_images.extend(Path(".").glob(pattern))
    
    png_contents = []
    if test_images:
        print(f"Found {len(test_images)} test images: {[img.name for img in test_images]}")
        for img_path in sorted(test_images)[:3]:  # Use up to 3 images
            content = img_path.read_bytes()
            png_contents.append(content)
            print(f"  - {img_path.name}: {len(content)} bytes")
    
    # Fill remaining slots or fallback if no images found
    fallback_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'
    
    while len(png_contents) < 3:
        png_contents.append(fallback_png)
        print("  - Added fallback PNG")
    
    # Create mock GDS content
    gds_content = b'''HEADER 5
BGNLIB 12 1 12 1 1 12 1 12 1
LIBNAME TESTLIB
UNITS 0.001 1e-09
BGNSTR 12 1 12 1 1 12 1 12 1
STRNAME TESTCELL
BOUNDARY
LAYER 1
DATATYPE 0
XY 0 0 1000 0 1000 1000 0 1000 0 0
ENDEL
ENDSTR
ENDLIB
'''
    
    # Create multiple mock files for batch testing (10+ images)
    num_results = 12  # Generate 12 layout/design pairs (24 files total)
    mock_files = []
    
    for i in range(1, num_results + 1):
        # Cycle through available images
        img_content = png_contents[(i - 1) % len(png_contents)]
        
        # Add PNG layout file
        mock_files.append({
            "name": f"layout_{i:03d}.png", 
            "content": img_content, 
            "type": "png", 
            "desc": f"Layout view {i}"
        })
        
        # Add corresponding GDS design file
        mock_files.append({
            "name": f"design_{i:03d}.gds", 
            "content": gds_content, 
            "type": "gds", 
            "desc": f"Design file {i}"
        })
    
    print(f"Generated {len(mock_files)} files ({len([f for f in mock_files if f['type'] == 'png'])} PNG, {len([f for f in mock_files if f['type'] == 'gds'])} GDS)")
    
    # Create ZIP file
    zip_filename = f"{task_id}_results.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_info in mock_files:
            zipf.writestr(file_info["name"], file_info["content"])
    
    # Create manifest
    manifest = {
        "batch_id": task_id,
        "created_at": datetime.now().isoformat(),
        "total_count": len(mock_files),
        "files": [
            {
                "filename": f["name"],
                "type": f["type"], 
                "description": f["desc"]
            } for f in mock_files
        ]
    }
    
    manifest_filename = f"{task_id}_manifest.json"
    with open(manifest_filename, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"Created batch files: {zip_filename} ({len(mock_files)} files), {manifest_filename}")
    return zip_filename, manifest_filename

def upload_mock_results(task_id: str):
    """Upload mock batch result files to Server B"""
    try:
        zip_file, manifest_file = create_mock_batch_files(task_id)
        
        print(f"Uploading mock batch results for task_id: {task_id}")
        
        with CustomFTP_TLS() as ftp:
            ftp.connect(FTP_CONFIG['host'], FTP_CONFIG['port'])
            ftp.auth()
            ftp.login(FTP_CONFIG['username'], FTP_CONFIG['password'])
            ftp.prot_p()
            ftp.set_pasv(True)
            ftp.cwd(FTP_CONFIG['download_dir'])
            
            # Upload ZIP file
            with open(zip_file, 'rb') as f:
                ftp.storbinary(f'STOR {zip_file}', f)
            print(f"✅ Uploaded {zip_file}")
            
            # Upload manifest file
            with open(manifest_file, 'rb') as f:
                ftp.storbinary(f'STOR {manifest_file}', f)
            print(f"✅ Uploaded {manifest_file}")
        
        # Clean up local files
        Path(zip_file).unlink()
        Path(manifest_file).unlink()
        
        print(f"✅ Mock batch results uploaded to Server B successfully!")
        
    except Exception as e:
        print(f"❌ Failed to upload mock batch results: {e}")

def list_server_files():
    """List files in Server B results directory"""
    try:
        with CustomFTP_TLS() as ftp:
            ftp.connect(FTP_CONFIG['host'], FTP_CONFIG['port'])
            ftp.auth()
            ftp.login(FTP_CONFIG['username'], FTP_CONFIG['password'])
            ftp.prot_p()
            ftp.set_pasv(True)
            ftp.cwd(FTP_CONFIG['download_dir'])
            
            files = ftp.nlst()
            print(f"Files in {FTP_CONFIG['download_dir']}:")
            zip_files = [f for f in files if f.endswith('.zip')]
            manifest_files = [f for f in files if f.endswith('.json')]
            other_files = [f for f in files if not f.endswith(('.zip', '.json'))]
            
            if zip_files:
                print("  📦 ZIP files:")
                for file in zip_files:
                    print(f"    - {file}")
            
            if manifest_files:
                print("  📄 Manifest files:")
                for file in manifest_files:
                    print(f"    - {file}")
                    
            if other_files:
                print("  📁 Other files:")
                for file in other_files:
                    print(f"    - {file}")
            
            if not files:
                print("    (No files found)")
        
    except Exception as e:
        print(f"❌ Failed to list server files: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_mock_results.py <task_id>    # Upload mock results")
        print("  python create_mock_results.py list         # List server files")
        sys.exit(1)
    
    if sys.argv[1] == "list":
        list_server_files()
    else:
        task_id = sys.argv[1]
        upload_mock_results(task_id)