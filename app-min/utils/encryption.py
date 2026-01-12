"""
Encryption utilities for sensitive configuration data.
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from flask import current_app


class EncryptionHelper:
    """Helper class to encrypt/decrypt sensitive configuration data"""

    @staticmethod
    def get_cipher():
        """Get encryption cipher using SECRET_KEY"""
        # Use first 32 bytes of SECRET_KEY as encryption key
        key = base64.urlsafe_b64encode(hashlib.sha256(current_app.config['SECRET_KEY'].encode()).digest())
        return Fernet(key)

    @staticmethod
    def encrypt(value):
        """Encrypt a string value"""
        if not value:
            return None
        try:
            cipher = EncryptionHelper.get_cipher()
            encrypted = cipher.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return value

    @staticmethod
    def decrypt(encrypted_value):
        """Decrypt an encrypted string value"""
        if not encrypted_value:
            return None
        try:
            cipher = EncryptionHelper.get_cipher()
            decrypted = cipher.decrypt(encrypted_value.encode())
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return encrypted_value
