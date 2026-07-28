# CWE-798: Hardcoded Credentials — fake secrets for Snyk Secret scan testing only.
GOOGLE_API_KEY = "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R"
RSA_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAx4fakeKeyMaterialForSnykSecretScanTestingOnly1234
5678notARealKeyDoNotUseAbCdEfGhIjKlMnOpQrStUvWxYz0123456789fake==
-----END RSA PRIVATE KEY-----"""


def main():
    print("Hello from example!")


if __name__ == "__main__":
    main()
