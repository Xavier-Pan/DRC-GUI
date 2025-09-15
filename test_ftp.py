import os
import ftplib
import ssl
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# FTP Configuration
FTP_CONFIG = {
    'host': os.getenv('FTP_SERVER_B_HOST'),
    'port': int(os.getenv('FTP_SERVER_B_PORT', '21')),
    'username': os.getenv('FTP_SERVER_B_USER'),
    'password': os.getenv('FTP_SERVER_B_PASS'),
    'upload_dir': os.getenv('FTP_SERVER_B_UPLOAD_DIR'),
}

class CustomFTP_TLS(ftplib.FTP_TLS):
    """Custom FTP_TLS class to handle TLS session reuse issues"""
    
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn,
                                          server_hostname=self.host,
                                          session=self.sock.session)  # Reuse TLS session
        return conn, size

def test_custom_ftp_tls():
    """Test with custom FTP_TLS that handles session reuse"""
    print("Testing with Custom FTP_TLS (session reuse)...")
    
    # Create test file
    test_file = Path("test_upload_custom.txt")
    test_file.write_text("Test upload with custom FTP_TLS")
    
    try:
        ftp = CustomFTP_TLS()
        ftp.connect(FTP_CONFIG['host'], FTP_CONFIG['port'])
        ftp.auth()
        ftp.login(FTP_CONFIG['username'], FTP_CONFIG['password'])
        ftp.prot_p()
        ftp.set_pasv(True)
        ftp.cwd(FTP_CONFIG['upload_dir'])
        
        # Upload file
        with open(test_file, 'rb') as f:
            ftp.storbinary(f'STOR {test_file.name}', f)
        
        ftp.quit()
        print("✅ Custom FTP_TLS upload successful!")
        return True
        
    except Exception as e:
        print(f"❌ Custom FTP_TLS failed: {e}")
        return False
    finally:
        test_file.unlink(missing_ok=True)

def test_implicit_tls():
    """Test with implicit TLS (port 990)"""
    print("Testing with Implicit TLS (port 990)...")
    
    # Create test file
    test_file = Path("test_upload_implicit.txt")
    test_file.write_text("Test upload with implicit TLS")
    
    try:
        # Try implicit TLS on port 990
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        ftp = ftplib.FTP_TLS(context=context)
        ftp.connect(FTP_CONFIG['host'], 990)  # Implicit TLS port
        ftp.login(FTP_CONFIG['username'], FTP_CONFIG['password'])
        ftp.prot_p()
        ftp.set_pasv(True)
        ftp.cwd(FTP_CONFIG['upload_dir'])
        
        # Upload file
        with open(test_file, 'rb') as f:
            ftp.storbinary(f'STOR {test_file.name}', f)
        
        ftp.quit()
        print("✅ Implicit TLS upload successful!")
        return True
        
    except Exception as e:
        print(f"❌ Implicit TLS failed: {e}")
        return False
    finally:
        test_file.unlink(missing_ok=True)

def test_no_data_protection():
    """Test with TLS auth but no data protection"""
    print("Testing with TLS auth but no data encryption...")
    
    # Create test file
    test_file = Path("test_upload_nodata.txt")
    test_file.write_text("Test upload without data protection")
    
    try:
        ftp = ftplib.FTP_TLS()
        ftp.connect(FTP_CONFIG['host'], FTP_CONFIG['port'])
        ftp.auth()
        ftp.login(FTP_CONFIG['username'], FTP_CONFIG['password'])
        # Don't call prot_p() - leave data channel unencrypted
        ftp.set_pasv(True)
        ftp.cwd(FTP_CONFIG['upload_dir'])
        
        # Upload file
        with open(test_file, 'rb') as f:
            ftp.storbinary(f'STOR {test_file.name}', f)
        
        ftp.quit()
        print("✅ TLS auth without data protection successful!")
        return True
        
    except Exception as e:
        print(f"❌ TLS auth without data protection failed: {e}")
        return False
    finally:
        test_file.unlink(missing_ok=True)

if __name__ == "__main__":
    print("=== Advanced FTP TLS Tests ===")
    
    success = False
    
    # Try different approaches
    if not success:
        success = test_custom_ftp_tls()
    
    if not success:
        success = test_no_data_protection()
    
    if not success:
        success = test_implicit_tls()
    
    if not success:
        print("\n❌ All FTP TLS methods failed.")
        print("Server may have very strict TLS requirements.")
    else:
        print("\n✅ Found working FTP configuration!")